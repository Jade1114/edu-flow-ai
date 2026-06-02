"""Compatibility wrapper for the V2 dual-ranker training entrypoint."""

from __future__ import annotations

from ml.training.train_room_ranker import train as train_room_ranker
from ml.training.train_slot_ranker import train as train_slot_ranker


def train():
    room_model = train_room_ranker()
    slot_model = train_slot_ranker()
    return room_model, slot_model


if __name__ == "__main__":
    train()
