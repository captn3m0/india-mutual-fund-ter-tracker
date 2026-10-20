from mastodon import Mastodon
import os
import sys

MAX_TOOT_LENGTH = 480
MAX_TOOTS = 5


def chunk_strings(strings, maxlength):
    chunks = []
    current_chunk = []
    current_length = 0
    for s in strings:
        if current_chunk and current_length + len(s) > maxlength:
            chunks.append(current_chunk)
            current_chunk = []
            current_length = 0
        current_chunk.append(s)
        current_length += len(s) + 1
    # Any leftovers?
    if current_chunk:
        chunks.append(current_chunk)
    return chunks


# read stdin and split it by line into a list
def get_toots():
    lines = [line for line in sys.stdin.read().splitlines() if line.strip()]
    chunks = chunk_strings(lines, MAX_TOOT_LENGTH)
    for chunk in chunks[:MAX_TOOTS]:
        yield post_text(chunk)
    if len(chunks) > MAX_TOOTS:
        remaining = sum(len(chunk) for chunk in chunks[MAX_TOOTS:])
        repo = os.environ.get("GITHUB_REPOSITORY", "captn3m0/india-mutual-fund-ter-tracker")
        yield f"…and {remaining} more TER changes: https://github.com/{repo}/releases/latest"


def post_text(lines):
    return "\n".join(lines)


if __name__ == "__main__":
    mastodon = Mastodon(
        api_base_url=os.environ["MASTODON_API_BASE_URL"],
        access_token=os.environ["MASTODON_ACCESS_TOKEN"],
    )
    for toot in get_toots():
        print("***")
        print(toot)
        mastodon.toot(toot)
        print("***")
