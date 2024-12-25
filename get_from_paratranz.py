
import json, os, requests, sys
import tempfile, logging
from zipfile import ZipFile
from time import sleep
from datetime import datetime

LOGGER = logging.getLogger("Atlyss 汉化文件生成器")
logging.basicConfig(level=logging.INFO, format='[%(asctime)s][%(name)s][%(levelname)s] %(message)s')

ROOT = os.path.dirname(os.path.abspath(__file__))
TOKEN = sys.argv[1]

HEADER = {
    'Authorization': TOKEN,
}

PROJECT_ID = 12591
API_URL = 'https://paratranz.cn/api'
STRINGS_EXPORT_DIR = os.path.join(ROOT,)
os.makedirs(STRINGS_EXPORT_DIR, exist_ok=True)


def request_helper(response, /,  err_hint:str|None=None, exit_on_error=True):
    if response.status_code != 200:
        if err_hint:
            LOGGER.error(err_hint)
        LOGGER.error(f"请求失败: {response.status_code}")
        LOGGER.error(response.text)
        valid = False
        if exit_on_error:
            sys.exit(1)
    else:
        valid = True
    return response, valid

# %% 检查是否需要构建
response, success = request_helper(
    requests.get(
        f'{API_URL}/projects/{PROJECT_ID}/artifacts',
        headers=HEADER
    ),
    err_hint="获取构建状态失败"
)
artifact_time = datetime.fromisoformat(response.json()['createdAt'])
artifact_id = response.json()['id']
    # %% 获取项目更新时间
response, success = request_helper(
    requests.get(
        f'{API_URL}/projects/{PROJECT_ID}/files',
        headers=HEADER
    ),
    err_hint="获取项目更新时间失败"
)
project_time = max([datetime.fromisoformat(file['modifiedAt']) for file in response.json()])

if artifact_time < project_time:
    LOGGER.info("检测到有新翻译，尝试构建 zip 文件")
    
    response, success = request_helper(
        requests.post(
            f'{API_URL}/projects/{PROJECT_ID}/artifacts',
            headers=HEADER
        ),
        err_hint="构建任务发布失败",
        exit_on_error=False
    )
    if success:
        LOGGER.info("构建任务已发布")
        # 如果最新构建 id 和 artifact_id 相同，则说明当前最新构建还是旧构建，需要等待构建完成
        while requests.get(f"{API_URL}/projects/{PROJECT_ID}/artifacts", headers=HEADER).json()['id'] == artifact_id:
            LOGGER.info(f"等待构建完成...")
            sleep(5)
        LOGGER.info("构建完成")
    elif response.status_code == 403:
        LOGGER.error("构建任务发布失败: 没有权限")
        
response, success = request_helper(
    requests.get(
        f'{API_URL}/projects/{PROJECT_ID}/artifacts',
        headers=HEADER
    ),
    err_hint="无法获取最后一次构建的时间"
)
if success:
    last_artifact_datetime = datetime.fromisoformat(response.json()['createdAt'])
        
        
with tempfile.TemporaryFile() as f:
    response = requests.get(
        f'{API_URL}/projects/{PROJECT_ID}/artifacts/download',
        headers=HEADER,
        stream=True
    )
    
    for chunk in response.iter_content(chunk_size=8192):
        f.write(chunk)
    
    LOGGER.info("下载完成，开始解析")
    
    f.seek(0)
    translation_data = []
    with ZipFile(f) as zipObj:
        for name in zipObj.namelist():
            if name.startswith('utf8/') and name.endswith('.json'):
                with zipObj.open(name) as json_file:
                    translation_data.extend(json.load(json_file))

with open(os.path.join(STRINGS_EXPORT_DIR, 'strings.tsv'), 'w', encoding='utf-8', newline='\n') as f:
    f.write('key\tvalue\n')
    for i18n_struct in translation_data:
        f.write(f'{i18n_struct["key"]}\t{i18n_struct["translation"]}\n' or i18n_struct["original"])
LOGGER.info("翻译文件转换完成")