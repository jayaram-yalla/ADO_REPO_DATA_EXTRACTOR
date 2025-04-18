from azure.devops.connection import Connection
from msrest.authentication import BasicAuthentication
from azure.devops.v7_1.git.models import GitQueryCommitsCriteria, GitVersionDescriptor
from azure.devops.v7_1.git.git_client import GitClient
from azure.devops.v7_1.project_analysis.project_analysis_client import ProjectAnalysisClient
from tabulate import tabulate
import jmespath
import sys
from collections import defaultdict
import re

# Read tenant and PAT
tenant = sys.argv[1]
personal_access_token = sys.argv[2]

# Utility Functions
def null_checker(x):
    try:
        return str(x) if x is not None else "empty"
    except Exception:
        return "empty"

def getFilesCount(repoName, jsondata):
    query = f"repository_language_analytics[?name == '{repoName}'].language_breakdown[].files"
    results = ",".join(str(i) for i in jmespath.search(query, jsondata))
    return str(results)

def getTechStack(repoName, jsondata):
    query = f"repository_language_analytics[?name == '{repoName}'].language_breakdown[].name"
    results = ",".join(jmespath.search(query, jsondata))
    return str(results)

# Setup Connection
organization_url = f"https://dev.azure.com/{tenant}"
credentials = BasicAuthentication("", personal_access_token)
connection = Connection(base_url=organization_url, creds=credentials)

# Clients
git_client_repos: GitClient = connection.clients.get_git_client()
git_client_repos_pac: ProjectAnalysisClient = connection.clients_v7_1.get_project_analysis_client()

# Get Repositories
repositories = git_client_repos.get_repositories()
print(f"total number of repos in {organization_url} tenant:{len(repositories)}")

# Basic Repo Metadata
repo_data = []
for repo in repositories:
    data = [
        null_checker(repo.name),
        null_checker(repo.id),
        null_checker(repo.project.name),
        null_checker(repo.project.id),
        null_checker(repo.web_url),
        null_checker(repo.default_branch),
        null_checker(str(repo.is_disabled)),
        null_checker(repo.project.description)
    ]
    repo_data.append(data)

# Initial HTML Output (basic repo + branch info)
row_headers = 'REPO NAME,REPO ID,PROJECT NAME,PROJECT ID,REPO URL,REPO DEFAULT BRANCH,REPO DISABLED STATE,PROJECT DESCRIPTION'.split(',')
htmloutput = tabulate(repo_data, row_headers, tablefmt="html", showindex="always")
with open(f"{tenant}_ADO_DATA_WITH_DEFAULT_BRANCH.html", "w", encoding="utf-8") as f:
    f.write(htmloutput)

# Project Language Analytics
project_ids = list(set([i[3] for i in repo_data]))
print(f"Unique projects: {len(project_ids)}")

lang_data = {}
for pid in project_ids:
    try:
        lang_info = git_client_repos_pac.get_project_language_analytics(pid)
        lang_data[lang_info.id] = lang_info.as_dict()
    except Exception as e:
        print(f"Language fetch failed for project {pid}: {e}")

# Save JSON dump
with open("all_projects_json_data.json", "w", encoding="utf-8") as f:
    f.write(str(lang_data))

# Append Language + File Count
final_repo_data = []
for i in repo_data:
    reponame = i[0]
    project_id = i[3]
    data = i
    data.append(getTechStack(reponame, lang_data.get(project_id, {})))
    data.append(getFilesCount(reponame, lang_data.get(project_id, {})))
    final_repo_data.append(data)

# CONTRIBUTORS: fetch from latest commits on default branch
MAX_COMMITS = 100
repo_contributors = defaultdict(set)
ci_patterns = re.compile(r"(bot|ci|build|pipeline|system)", re.IGNORECASE)

print("Fetching enriched contributor details for each repository...")

for repo in repositories:
    branch = repo.default_branch
    if not branch:
        print(f"Skipping {repo.name} - No default branch.")
        continue

    branch_name = branch.replace("refs/heads/", "")

    try:
        criteria = GitQueryCommitsCriteria(
            item_version=GitVersionDescriptor(
                version=branch_name,
                version_type="branch"
            )
        )

        commits = git_client_repos.get_commits(
            repository_id=repo.id,
            project=repo.project.id,
            search_criteria=criteria,
            top=MAX_COMMITS
        )

        for commit in commits:
            name = commit.author.name if commit.author and commit.author.name else ""
            email = commit.author.email if commit.author and commit.author.email else ""

            if not name and commit.committer:
                name = commit.committer.name or ""
                email = commit.committer.email or ""

            contributor = f"{name.strip()} <{email.strip()}>" if name and email else name.strip()

            if not contributor or ci_patterns.search(contributor):
                continue

            repo_contributors[repo.name].add(contributor)

    except Exception as e:
        print(f"Error fetching commits for {repo.name}: {e}")

# Append contributors to final data
for row in final_repo_data:
    repo_name = row[0]
    contributors = sorted(list(repo_contributors.get(repo_name, [])))
    row.append(", ".join(contributors) if contributors else "N/A")

# Final HTML Output with contributors
row_headers = 'REPO NAME,REPO ID,PROJECT NAME,PROJECT ID,REPO URL,REPO DEFAULT BRANCH,REPO DISABLED STATE,PROJECT DESCRIPTION,LANUGAGE STACK,TOTAL NUMBER OF FILES,CONTRIBUTORS'.split(',')
htmloutput = tabulate(final_repo_data, row_headers, tablefmt="html", showindex="always")
with open(f"{tenant}_ADO_DATA_WITH_DEVS.html", "w", encoding="utf-8") as f:
    f.write(htmloutput)
