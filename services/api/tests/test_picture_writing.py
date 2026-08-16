from uuid import uuid4

import pytest

from study_api.picture_writing import InMemoryPictureWritingRepository
from study_api.privacy_models import PictureWritingGuide


def _guide() -> PictureWritingGuide:
    return PictureWritingGuide(
        scene_observations=("小猫坐在窗边。", "窗外有一棵树。"),
        focus_questions=("你看到了谁？", "它在什么地方？"),
        sentence_starters=("图上有", "我发现"),
        detail_prompts=("再说说动作。", "想想先后顺序。"),
        confidence=0.8,
    )


def test_picture_writing_guide_is_child_scoped_and_idempotent() -> None:
    repository = InMemoryPictureWritingRepository()
    household_id, capture_id, child_id = uuid4(), uuid4(), uuid4()
    record, replayed = repository.create(
        household_id,
        capture_id,
        child_id,
        "picture-writing-capture-1",
        _guide(),
        provider="newapi",
        model="vision-model",
    )
    same, replayed_same = repository.create(
        household_id,
        capture_id,
        child_id,
        "picture-writing-capture-1",
        _guide(),
        provider="newapi",
        model="vision-model",
    )

    assert replayed is False
    assert replayed_same is True
    assert same.id == record.id
    assert repository.get(household_id, capture_id, child_id, record.id) == record
    with pytest.raises(LookupError):
        repository.get(household_id, capture_id, uuid4(), record.id)
