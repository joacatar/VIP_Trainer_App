from typing import Literal, TypedDict


class Profile(TypedDict):
    id: str
    role: Literal["trainer", "trainee"]
    full_name: str


class Trainee(TypedDict):
    id: str
    full_name: str
    current_phase: str
    start_date: str
