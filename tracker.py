import requests
import os
import json
import sys


def print_flush(*args, **kwargs):
    kwargs["flush"] = True
    print(*args, **kwargs)


def get_stargazers(
    repo_owner: str, repo_name: str, action_token: str, personal_token: str
):
    is_complete = True
    max_page_items = 100
    url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/stargazers"
    # vnd.github.v3.star+json -> with timestamp
    # vnd.github+json -> no timestamp
    headers = {"Accept": "application/vnd.github.v3.star+json"}

    usernames = []
    page = 1

    while True:
        params = {"page": page, "per_page": max_page_items}
        response = requests.get(url, headers=headers, params=params)

        if response.status_code == 200:
            stargazers = response.json()
            for user in stargazers:
                userid = user["user"]["id"]
                username = user["user"]["login"]
                starred_at = user["starred_at"]
                usernames.append(
                    {"id": userid, "username": username, "starred_at": starred_at}
                )
            if len(stargazers) < max_page_items:
                break
            page += 1
        else:
            print_flush("Warning: Unexpected response:", response.status_code)
            if response.status_code < 500:
                if not "Authorization" in headers.keys():
                    headers["Authorization"] = f"Bearer {action_token}"
                    print_flush("Warning: Using action token")
                    continue
                elif headers["Authorization"].endswith(action_token):
                    headers["Authorization"] = f"Bearer {personal_token}"
                    print_flush("Warning: Using personal token")
                    continue
                else:
                    print_flush("Error: All tokens have been used")
            is_complete = False
            break

    return usernames, is_complete


# gist_content = {
#     filename1: {"content": content1},
#     filename2: {"content": content2},
#     ......
# }
def update_gist(gist_id: str, gist_content: dict, access_token: str):
    url = f"https://api.github.com/gists/{gist_id}"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/vnd.github.v3+json",
    }
    data = {"files": gist_content}

    response = requests.patch(url, headers=headers, json=data)

    if response.status_code == 200:
        print_flush("Info: Gist Updated")
        return True
    else:
        print_flush("Error: Failed to update Gist:", response.status_code)
        return False


if __name__ == "__main__":
    # load secrets
    personal_token = os.environ["MY_TOKEN"]
    action_token = os.environ["GITHUB_TOKEN"]
    gist_id = os.environ["GIST_ID"]

    # load target repos
    with open("repos.json", "r") as f:
        repos = json.load(f)

    # process every repo
    gist_content = {}
    if len(repos) == 0:
        print_flush("Warning: No repos")
    for repo in repos:
        star_info, is_complete = get_stargazers(
            repo["owner"], repo["name"], action_token, personal_token
        )
        if not is_complete:
            print_flush(
                f"Error: {repo['owner']}/{repo['name']}: Failed to get the stars"
            )
            continue
        else:
            star_num = len(star_info)
            print_flush(f"Info: {repo['owner']}/{repo['name']}: {star_num} star(s)")

            filename = f"{repo['owner']}#{repo['name']}"
            content = ""
            for stargazer in star_info:
                line = str(stargazer["id"]) + ","
                line += stargazer["username"] + ","
                line += stargazer["starred_at"] + "\n"
                content += line
            gist_content[filename] = {"content": content}

    # update gists
    if len(gist_content) == 0:
        print_flush("Warning: Nothing to write")
    else:
        if not update_gist(gist_id, gist_content, personal_token):
            sys.exit(1)
