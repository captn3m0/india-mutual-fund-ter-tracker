from mastodon import Mastodon
import os
import sys

MAX_TOOT_LENGTH = 480

def chunk_strings(strings, maxlength):
    chunks = []
    current_chunk = []
    current_length = 0
    for s in strings:
        if current_length + len(s) > maxlength:
            chunks.append(current_chunk)
            current_chunk = []
            current_length = 0
        current_chunk.append(s)
        current_length += len(s)
    # Any leftovers?
    if current_chunk:
        chunks.append(current_chunk)
    return chunks

# read stdin and split it by line into a list
def get_toots():
    lines = sys.stdin.read().splitlines()
    print(lines)
    print(chunk_strings(lines, MAX_TOOT_LENGTH))
    for chunk in chunk_strings(lines, MAX_TOOT_LENGTH):
        yield post_text(chunk)

def post_text(lines):
    return "\n".join(lines)

if __name__ == '__main__':
    mastodon = Mastodon(
        api_base_url = os.environ['MASTODON_API_BASE_URL'],
        access_token = os.environ['MASTODON_ACCESS_TOKEN']
    )
    for toot in get_toots():
        print("***")
        print(toot)
        # mastodon.toot(toot)
        print("***")