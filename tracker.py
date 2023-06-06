import requests
import os
import json
import sys
import difflib
import aiohttp
import asyncio
from typing import Any
import math


def print_flush(*args, **kwargs):
    kwargs["flush"] = True
    print(*args, **kwargs)


def get_repo_star_count(owner, repo, access_token):
    url = f"https://api.github.com/repos/{owner}/{repo}"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/vnd.github.v3+json",
    }

    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        star_count = data.get("stargazers_count")
        return star_count
    else:
        return -1


async def get_stargazers_task(session: Any, page: int, context: dict):
    # status:
    # 0:ok
    # 1:using action token, ok
    # 2:using personal token, ok
    # 3:error
    status = 0
    # vnd.github.v3.star+json -> with timestamp
    # vnd.github+json -> no timestamp
    headers = {"Accept": "application/vnd.github.v3.star+json"}
    if context["token_status"] == 0:
        pass
    elif context["token_status"] == 1:
        headers["Authorization"] = f"Bearer {context['action_token']}"
        status = 1
    elif context["token_status"] == 2:
        headers["Authorization"] = f"Bearer {context['personal_token']}"
        status = 2

    params = {"page": page, "per_page": context["max_page_items"]}
    url = f"https://api.github.com/repos/{context['repo_owner']}/{context['repo_name']}/stargazers"
    star_info = []
    while True:
        async with session.get(url, headers=headers, params=params) as response:
            if response.status == 200:
                stargazers = await response.json()
                for user in stargazers:
                    userid = user["user"]["id"]
                    username = user["user"]["login"]
                    starred_at = user["starred_at"]
                    star_info.append(
                        {"id": userid, "username": username, "starred_at": starred_at}
                    )
                break
            else:
                if response.status == 403:
                    if status == 0:
                        headers["Authorization"] = f"Bearer {context['action_token']}"
                        status = 1
                        continue
                    elif status == 1:
                        headers["Authorization"] = f"Bearer {context['personal_token']}"
                        status = 2
                        continue
                    else:
                        print_flush("Error: All tokens have been used")
                else:
                    print_flush("Warning: Unexpected response:", response.status)
                status = 3
                break
    return star_info, status


async def get_stargazers_collector(context: dict):
    parallel_num = 10
    page = 1
    max_page = get_repo_star_count(
        context["repo_owner"], context["repo_name"], context["personal_token"]
    )
    if max_page >= 0:
        max_page = math.ceil(max_page / context["max_page_items"])
    else:
        return

    star_info = []
    async with aiohttp.ClientSession() as session:
        while True:
            tasks = []
            # process with async tasks
            for _ in range(min(parallel_num, max_page - page + 1)):
                task = asyncio.create_task(get_stargazers_task(session, page, context))
                page += 1
                tasks.append(task)
            results = await asyncio.gather(*tasks)
            # handle results
            for info, status in results:
                star_info.extend(info)
                if status > context["token_status"]:
                    context["token_status"] = status
                    if status == 3:
                        print_flush("Error: one of the task fails")
                    elif status == 2:
                        print_flush(
                            f"Warning: {context['repo_owner']}/{context['repo_name']}: Using personal token around page {page}"
                        )
                    elif status == 1:
                        print_flush(
                            f"Warning: {context['repo_owner']}/{context['repo_name']}: Using action token around page {page}"
                        )
                if len(info) == 0:
                    context["token_status"] = 3
                if context["token_status"] == 3:
                    break

            # break if error occurs or finished
            if context["token_status"] == 3 or page > max_page:
                break
    return star_info, context["token_status"]


def get_stargazers(
    repo_owner: str,
    repo_name: str,
    action_token: str,
    personal_token: str,
    last_status: int = 0,
):
    max_page_items = 100
    context = {
        "repo_owner": repo_owner,
        "repo_name": repo_name,
        "max_page_items": max_page_items,
        "action_token": action_token,
        "personal_token": personal_token,
        "token_status": last_status,  # aka "status"
    }

    return asyncio.run(get_stargazers_collector(context))


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
    last_status = 0
    gist_content = {}
    if len(repos) == 0:
        print_flush("Warning: No repos")
    for repo in repos:
        owner = ""
        name = ""
        if type(repo) == str:
            owner, name = repo.split("/")
        elif type(repo) == dict and ("owner" and "name" in repo.keys()):
            owner = repo["owner"]
            name = repo["name"]
        if len(owner) == 0 or len(name) == 0:
            print_flush("Error: Cannot treat item as repo:", repo)
            continue

        star_info, last_status = get_stargazers(
            owner, name, action_token, personal_token, last_status
        )
        if last_status == 3:  # error occurs
            print_flush(f"Error: {owner}/{name}: Failed to get the stars")
            continue
        else:
            star_num = len(star_info)
            print_flush(f"Info: {owner}/{name}: {star_num} star(s)")

            filename = f"{owner}#{name}"
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
                print_flush(f"Info: {owner}/{name}: Need update")

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
