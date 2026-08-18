"""Quantitative evaluation of a face-swapped video against the source identity.

Usage:
    uv run python tools/evaluate_swap.py \
        --source faces/shan_1.jpeg \
        --target output/My-Movie-1-faceswap-shan-run-03.mov \
        --samples 200 \
        --csv output/eval-run-03.csv
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Optional

import numpy as np

from facefusion import face_creator, face_detector, face_landmarker, face_recognizer, logger, state_manager
from facefusion.args import apply_args
from facefusion.face_selector import calculate_face_distance
from facefusion.program import create_program
from facefusion.types import Face
from facefusion.vision import count_video_frame_total, detect_video_fps, read_static_image, read_video_frame


def init_state(source: str, target: str) -> None:
    program = create_program()
    args = vars(program.parse_args(['headless-run', '-s', source, '-t', target, '-o', '/tmp/_eval_unused.mov']))
    apply_args(args, state_manager.init_item)
    logger.init(state_manager.get_item('log_level'))

    if not (face_detector.pre_check() and face_landmarker.pre_check() and face_recognizer.pre_check()):
        raise RuntimeError('model pre_check failed (download/hash mismatch)')


def source_embedding(source_path: str) -> np.ndarray:
    image = read_static_image(source_path)
    if image is None:
        raise RuntimeError(f'could not read source image: {source_path}')
    faces = face_creator.get_many_faces([image])
    if not faces:
        raise RuntimeError('no face detected in source image')
    return np.asarray(faces[0].embedding_norm)


def best_face_by_detector(faces: list[Face]) -> Optional[Face]:
    if not faces:
        return None
    return max(faces, key=lambda f: f.score_set.get('detector', 0.0))


def best_face_by_source_match(faces: list[Face], src_emb: np.ndarray) -> Optional[Face]:
    if not faces:
        return None
    return min(faces, key=lambda f: 1.0 - float(np.dot(src_emb, f.embedding_norm)))


def build_indices(total_frames: int, samples: int, start_frame: Optional[int], end_frame: Optional[int], stride: Optional[int]) -> list[int]:
    if start_frame is not None or end_frame is not None or stride is not None:
        lo = max(1, start_frame or 1)
        hi = min(total_frames, end_frame or total_frames)
        step = stride or 1
        return list(range(lo, hi + 1, step))
    return np.linspace(1, total_frames, num=min(samples, total_frames), dtype=int).tolist()


def evaluate(source: str, target: str, samples: int, csv_path: Optional[str], ref_match: bool, start_frame: Optional[int], end_frame: Optional[int], stride: Optional[int]) -> None:
    init_state(source, target)
    src_emb = source_embedding(source)

    total_frames = count_video_frame_total(target)
    fps = detect_video_fps(target) or 0.0
    if total_frames <= 0:
        raise RuntimeError(f'could not read frame count from {target}')

    sample_indices = build_indices(total_frames, samples, start_frame, end_frame, stride)
    selector_label = 'source-match (closest cosine to source)' if ref_match else 'max detector score'

    rows = []
    for idx in sample_indices:
        frame = read_video_frame(target, idx)
        if frame is None:
            rows.append({'frame': idx, 'detected': 0, 'face_count': 0, 'detector_score': None, 'landmarker_score': None, 'cosine_distance': None})
            continue
        faces = face_creator.get_many_faces([frame])
        face = best_face_by_source_match(faces, src_emb) if ref_match else best_face_by_detector(faces)
        if face is None:
            rows.append({'frame': idx, 'detected': 0, 'face_count': 0, 'detector_score': None, 'landmarker_score': None, 'cosine_distance': None})
            continue
        cosine = 1.0 - float(np.dot(src_emb, face.embedding_norm))
        rows.append({
            'frame': idx,
            'detected': 1,
            'face_count': len(faces),
            'detector_score': float(face.score_set.get('detector', 0.0)),
            'landmarker_score': float(face.score_set.get('landmarker', 0.0)),
            'cosine_distance': cosine,
        })

    detected = [r for r in rows if r['detected']]
    distances = np.array([r['cosine_distance'] for r in detected]) if detected else np.array([])
    det_scores = np.array([r['detector_score'] for r in detected]) if detected else np.array([])
    lm_scores = np.array([r['landmarker_score'] for r in detected]) if detected else np.array([])

    print(f'video:           {target}')
    print(f'  frames total:  {total_frames}')
    print(f'  fps:           {fps:.3f}')
    print(f'  sampled:       {len(rows)}')
    print(f'  selector:      {selector_label}')
    print(f'  detected:      {len(detected)} ({100.0 * len(detected) / max(len(rows), 1):.1f}%)')
    if detected:
        face_counts = [r['face_count'] for r in detected]
        multi = sum(1 for c in face_counts if c > 1)
        print(f'  multi-face:    {multi}/{len(detected)} detected frames had >1 face')
    if len(distances):
        print(f'cosine distance to source (lower = closer to source identity):')
        print(f'  mean:          {distances.mean():.4f}')
        print(f'  median:        {np.median(distances):.4f}')
        print(f'  p05:           {np.percentile(distances, 5):.4f}')
        print(f'  p95:           {np.percentile(distances, 95):.4f}')
        print(f'  min:           {distances.min():.4f}')
        print(f'  max:           {distances.max():.4f}')
        for thresh in (0.4, 0.5, 0.6, 0.7):
            below = (distances < thresh).sum()
            print(f'  < {thresh}:        {below}/{len(distances)} ({100.0 * below / len(distances):.1f}%)')
    if len(det_scores):
        print(f'detector score: mean {det_scores.mean():.3f}  min {det_scores.min():.3f}')
    if len(lm_scores):
        print(f'landmarker score: mean {lm_scores.mean():.3f}  min {lm_scores.min():.3f}')

    if csv_path:
        Path(csv_path).parent.mkdir(parents=True, exist_ok=True)
        with open(csv_path, 'w', newline='') as fh:
            writer = csv.DictWriter(fh, fieldnames=['frame', 'detected', 'face_count', 'detector_score', 'landmarker_score', 'cosine_distance'])
            writer.writeheader()
            writer.writerows(rows)
        print(f'wrote {csv_path}')


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', required=True)
    parser.add_argument('--target', required=True)
    parser.add_argument('--samples', type=int, default=200)
    parser.add_argument('--csv', default=None)
    parser.add_argument('--ref-match', action='store_true', help='select per-frame face by closest cosine to source embedding (mirrors swap-pipeline reference selector); default picks max detector score')
    parser.add_argument('--start-frame', type=int, default=None, help='windowed eval: first frame (1-indexed)')
    parser.add_argument('--end-frame', type=int, default=None, help='windowed eval: last frame (inclusive)')
    parser.add_argument('--stride', type=int, default=None, help='windowed eval: frame step (1 = every frame)')
    args = parser.parse_args()
    evaluate(args.source, args.target, args.samples, args.csv, args.ref_match, args.start_frame, args.end_frame, args.stride)


if __name__ == '__main__':
    main()
