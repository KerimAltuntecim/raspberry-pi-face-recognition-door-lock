"""Erişim uygulamasındaki durum geçişlerini anlatan sade örnek."""

from enum import Enum, auto


class AccessState(Enum):
    MENU = auto()
    VERIFYING = auto()
    CHALLENGE_REQUIRED = auto()
    UNLOCKED = auto()
    REJECTED = auto()


def next_state(state: AccessState, event: str) -> AccessState:
    """Model eşikleri ve kullanıcı verileri olmadan durum akışını gösterir."""
    transitions = {
        (AccessState.MENU, "start_verify"): AccessState.VERIFYING,
        (AccessState.VERIFYING, "match"): AccessState.CHALLENGE_REQUIRED,
        (AccessState.VERIFYING, "no_match"): AccessState.REJECTED,
        (AccessState.CHALLENGE_REQUIRED, "challenge_ok"): AccessState.UNLOCKED,
        (AccessState.CHALLENGE_REQUIRED, "challenge_failed"): AccessState.REJECTED,
        (AccessState.UNLOCKED, "timeout"): AccessState.MENU,
        (AccessState.REJECTED, "acknowledge"): AccessState.MENU,
    }
    return transitions.get((state, event), state)
