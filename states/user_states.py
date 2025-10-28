from enum import Enum

class UserState(Enum):
    START = 0
    AWAITING_CHOICE = 1
    AWAITING_FEEDBACK = 2
    AWAITING_QUESTION = 3  # Объединенное состояние для вопроса