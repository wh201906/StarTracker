import requests
import os
import json
import sys
import difflib


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


def get_gist_file_content(gist_id: str, filename: str):
    url = f"https://api.github.com/gists/{gist_id}"
    response = requests.get(url)

    if response.status_code == 200:
        gist_data = response.json()
        files = gist_data.get("files")
        if not files:
            print_flush('Error: get_gist_file_content(): No "files"')
            return None
        if filename not in files:
            print_flush("Error: get_gist_file_content(): file not found")
            return None
        content = files[filename]["content"]
        return content
    else:
        print_flush("Error: Failed to get Gist:", response.status_code)
        return None


def get_rate_limit(access_token=None):
    url = "https://api.github.com/rate_limit"
    headers = {"Accept": "application/vnd.github.v3+json"}
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"

    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        rate_limit_data = response.json()
        return rate_limit_data["resources"]["core"]["remaining"]
    else:
        print_flush("Error: Failed to get limit:", response.status_code)
        return 0


if __name__ == "__main__":
    exit_code = 0
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
            new_content = []
            for stargazer in star_info:
                line = str(stargazer["id"]) + ","
                line += stargazer["username"] + ","
                line += stargazer["starred_at"] + "\n"
                new_content.append(line)

            old_content = get_gist_file_content(gist_id, filename)
            need_update = False
            if old_content is None:
                print_flush("Warning: No history data")
                need_update = True
            else:
                old_content = old_content.splitlines(keepends=True)
                diff_result = difflib.ndiff(old_content, new_content)
                lost = 0
                new = 0
                for item in diff_result:
                    if item.startswith("- "):
                        lost += 1
                    elif item.startswith("+ "):
                        new += 1
                if lost != 0:
                    print_flush(f"Info: Lost {lost} star(s)")
                    need_update = True
                if new != 0:
                    print_flush(f"Info: Get {new} star(s)")
                    need_update = True

            if need_update:
                content = ""
                for line in new_content:
                    content += line
                gist_content[filename] = {"content": content}
                print_flush(f"Info: {repo['owner']}/{repo['name']}: Need update")

    # update gists
    if len(gist_content) == 0:
        print_flush("Warning: Nothing to write")
    else:
        if not update_gist(gist_id, gist_content, personal_token):
            exit_code = 1

    print_flush("Info: Rate limit without authorization:", get_rate_limit())
    print_flush("Info: Rate limit for action token:", get_rate_limit(action_token))
    print_flush("Info: Rate limit for personal token:", get_rate_limit(personal_token))
    sys.exit(exit_code)
