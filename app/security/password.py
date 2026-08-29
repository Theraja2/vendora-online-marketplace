from pwdlib import PasswordHash

password_hash = PasswordHash.recommended()


# Verifying a login for a username that does not exist used to return before any
# hashing happened, which made unknown users answer ~36x faster than real ones and
# leaked which usernames are registered. The miss path now verifies against this
# throwaway hash so both paths pay the same Argon2 cost.
_DUMMY_HASH = password_hash.hash("vendora-dummy-password-for-constant-time-compare")


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(
    plain_password: str,
    hashed_password: str,
) -> bool:
    return password_hash.verify(
        plain_password,
        hashed_password,
    )


def waste_time_like_a_real_verify() -> None:
    """Burn the same Argon2 cost as a real verify, for the user-not-found path."""
    password_hash.verify("wrong-password", _DUMMY_HASH)
