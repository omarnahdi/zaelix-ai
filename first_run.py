import time
from email_agent import mistral_agent

def countdown(seconds: int, message: str) -> None:
    """Display a visible countdown before starting an agent run."""
    for remaining in range(seconds, 0, -1):
        print(
            f"\r⏳ {message} in {remaining:02d} second(s)...",
            end="",
            flush=True,
        )
        time.sleep(1)

    print(f"\r🚀 {message} now!{' ' * 30}\n")


# ─────────────────────────────────────────────
# Personal Inbox Setup
# ─────────────────────────────────────────────
print("\n" + "=" * 65)
print("📧 PERSONAL INBOX CREDENTIALS SETUP")
print("=" * 65)
print(
    "IMPORTANT — PLEASE READ CAREFULLY:\n\n"
    "A browser window will open for PERSONAL inbox authentication.\n"
    "You MUST sign in using your PERSONAL email account.\n\n"
    "Complete the sign-in process and grant the required permissions\n"
    "to generate credentials for your personal inbox.\n\n"
    "⚠️  Do NOT sign in with your work email account during this step."
)
print("=" * 65 + "\n")

countdown(12, "Starting PERSONAL inbox setup")

mistral_agent.print_response("Fetch an email from personal inbox")


# ─────────────────────────────────────────────
# Work Inbox Setup
# ─────────────────────────────────────────────
print("\n" + "=" * 65)
print("💼 WORK INBOX CREDENTIALS SETUP")
print("=" * 65)
print(
    "IMPORTANT — PLEASE READ CAREFULLY:\n\n"
    "A browser window will open for WORK inbox authentication.\n"
    "You MUST sign in using your WORK email account.\n\n"
    "Complete the sign-in process and grant the required permissions\n"
    "to generate credentials for your work inbox.\n\n"
    "⚠️  Do NOT sign in with your personal email account during this step."
)
print("=" * 65 + "\n")

countdown(12, "Starting WORK inbox setup")

mistral_agent.print_response("Fetch an email from work inbox")