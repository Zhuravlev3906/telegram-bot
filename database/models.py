from enum import Enum

class UserState(Enum):
    START = 0
    AWAITING_CHOICE = 1
    AWAITING_FEEDBACK = 2
    AWAITING_QUESTION_TEXT = 3
    AWAITING_QUESTION_PHOTOS = 4

class RequestStatus(Enum):
    NEW = 'new'
    IN_PROGRESS = 'in_progress'
    ANSWERED = 'answered'
    CLOSED = 'closed'