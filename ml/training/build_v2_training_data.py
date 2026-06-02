"""Compatibility wrapper for V2 dual-ranker sample generation."""

from __future__ import annotations

from ml.training.build_room_ranker_training_data import build as build_room_samples
from ml.training.build_slot_ranker_training_data import build as build_slot_samples


def build():
    room_samples = build_room_samples()
    slot_samples = build_slot_samples()
    return room_samples, slot_samples


if __name__ == "__main__":
    build()
