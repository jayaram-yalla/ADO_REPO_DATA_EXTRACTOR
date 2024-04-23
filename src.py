from azure.devops.connection import Connection
from msrest.authentication import BasicAuthentication
from azure.devops.v7_1.git.models import GitVersionDescriptor
from tabulate import tabulate
import jmespath
import sys

tenant=sys.argv[1]
personal_access_token = sys.argv[2]

def null_checker(x):
    return_data=''
    try:
        if x == None:
            return_data="empty"
        else:
            return_data=str(x)
    except Exception:
        return_data="empty"
    return return_data

def getFilesCount(repoName,jsondata):
    jmespath_files_number_search="repository_language_analytics[?name == '%s'].language_breakdown[].files" % repoName
    results=",".join(str(i) for i in jmespath.search(jmespath_files_number_search,jsondata))
    return str(results)

def getTechStack(repoName,jsondata):
    jmespath_tech_search="repository_language_analytics[?name == '%s'].language_breakdown[].name" % repoName
    results=",".join(jmespath.search(jmespath_tech_search,jsondata))
    return str(results)

organization_url = "https://dev.azure.com/"+tenant
credentials = BasicAuthentication("", personal_access_token)
connection = Connection(base_url=organization_url, creds=credentials)
git_client_repos = connection.clients.get_git_client()
repositories = git_client_repos.get_repositories()

print("total number of repos in %s tenant:%s" % (organization_url,str(len(repositories))))
repo_data=[]

for repo in repositories:
    data=[null_checker(repo.name),null_checker(repo.id),null_checker(repo.project.name),null_checker(repo.project.id),null_checker(repo.web_url),null_checker(repo.default_branch),null_checker(str(repo.is_disabled)),null_checker(repo.project.description)]
    repo_data.append(data)

row_headers='REPO NAME,REPO ID,PROJECT NAME,PROJECT ID,REPO URL,REPO DEFAULT BRANCH,REPO DISABLED STATE,PROJECT DESCRIPTION'.split(',')
htmloutput=tabulate(repo_data,row_headers,tablefmt="html",showindex="always")
f=open("%s_ADO_DATA_WITH_DEFAULT_BRANCH.html" % tenant,"w")
f.writelines(htmloutput)
f.close()

project=[]
for i in range(len(repo_data)):
    project.append(repo_data[i][2])
final_projects=list(set(project))
print(len(final_projects))

js={}
git_client_repos_pac=connection.clients_v7_1.get_project_analysis_client()
for i in final_projects:
    try:
        m=git_client_repos_pac.get_project_language_analytics(i)
        js.update({m.id:m.as_dict()})
    except Exception:
        print("not able to fetch details for:"+i)
print(len(js))
ld=str(js)
f=open("all_projects_json_data.json","w")
f.writelines(ld)
f.close()

final_repo_data=[]
for i in repo_data:
    reponame=i[0]
    project_id=i[3]
    data=i
    data.append(getTechStack(reponame,js[project_id]))
    data.append(getFilesCount(reponame,js[project_id]))
    final_repo_data.append(data)

row_headers='REPO NAME,REPO ID,PROJECT NAME,PROJECT ID,REPO URL,REPO DEFAULT BRANCH,REPO DISABLED STATE,PROJECT DESCRIPTION,LANUGAGE STACK,TOTAL NUMBER OF FILES'.split(',')
htmloutput=tabulate(final_repo_data,row_headers,tablefmt="html",showindex="always")
f=open("%s_ADO_DATA_WITH_DEFAULT_BRANCH_LANGUAGE_DATA.html" % tenant,"w")
f.writelines(htmloutput)
f.close()
