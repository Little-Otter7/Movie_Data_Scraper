import requests
from bs4 import BeautifulSoup
import json
import re
import os
from tqdm import tqdm

def crawl_movie_data(url):
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/115.0.0.0 Safari/537.36"
        )
    }
    resp = requests.get(url, headers=headers)
    if resp.status_code != 200:
        print(f"请求失败，状态码: {resp.status_code}")
        return None

    soup = BeautifulSoup(resp.text, 'html.parser')

    # 1. 获取电影标题
    movie_title_tag = soup.find('h1', class_='nav-header')
    movie_title = movie_title_tag.get_text(strip=True) if movie_title_tag else ""

    # 2. 获取页面中嵌入的 JSON 数据
    script_tag = soup.find('script', id='pageData', type='application/json')
    page_data_json = json.loads(script_tag.string) if script_tag else {}

    # 3. 提取基本信息
    basic_info = {}
    info_detail_cols = soup.select('div.info-detail-col')
    for col in info_detail_cols:
        title_tag = col.find('p', class_='info-detail-title')
        content_tag = col.find('p', class_='info-detail-content')
        if title_tag and content_tag:
            key = title_tag.get_text(strip=True)
            val = content_tag.get_text(strip=True)
            basic_info[key] = val
    if 'movieName' in page_data_json:
        basic_info["电影名称"] = page_data_json.get("movieName")

    # 4.1 提取日想看数据（映前）
    pre_wish_series = []
    wish_points = page_data_json.get("wishData", {}).get("series", [])[0].get("points", [])
    for point in wish_points:
        pre_wish_series.append({
            "date": point.get("xValue"),
            "wish_count": point.get("yValue")
        })

    # 4.2 提取评分信息
    rating_info = {}
    score_block = soup.find('div', class_='score-block-content')
    if score_block:
        rating_tag = score_block.find('span', class_='rating-num')
        rating_count_tag = score_block.find('p', class_='detail-score-count')
        wish_count_tag = score_block.find('p', class_='detail-wish-count')
        imdb_tag = score_block.find('p', class_='detail-other-score')

        if rating_tag:
            rating_info["rating"] = rating_tag.get_text(strip=True)
        if rating_count_tag:
            rating_info["rating_count"] = rating_count_tag.get_text(strip=True)
        if wish_count_tag:
            rating_info["wish_count"] = wish_count_tag.get_text(strip=True)
        if imdb_tag:
            imdb_text = imdb_tag.get_text(strip=True)
            if "IMDb" in imdb_text:
                rating_info["imdb_score"] = imdb_text.split("IMDb")[-1].strip()

    # 5. 提取日票房数据
    box_chart = page_data_json.get("boxshowChartData", {}).get("chartData", {}).get("box", {})
    box_office_series = []
    dates = box_chart.get("date", [])
    real = box_chart.get("real", [])
    forecast = box_chart.get("forecast", [])
    for d, r, f in zip(dates, real, forecast):
        box_office_series.append({
            "date": d,
            "box_office_real": r,
            "box_office_forecast": f
        })

    # 6. 提取日排片数据
    schedule_chart = page_data_json.get("boxshowChartData", {}).get("chartData", {}).get("show", {})
    schedule_series = []
    show_dates = schedule_chart.get("date", [])
    schedule_counts = schedule_chart.get("real", [])
    for d, c in zip(show_dates, schedule_counts):
        schedule_series.append({
            "date": d,
            "schedule_count": c
        })

    # 7. 用户画像
    persona_data = {}
    persona_section = soup.find('section', class_='persona-section')
    if persona_section:
        for item in persona_section.select('div.persona-line-item, div.persona-block.hotarea div.persona-item'):
            key_tag = item.find('div', class_='persona-item-key')
            val_tag = item.find('div', class_='persona-item-value')
            if key_tag and val_tag:
                persona_data[key_tag.get_text(strip=True)] = val_tag.get_text(strip=True)

    # 8. 导演、演员、编剧
    cast_info = {"导演": [], "演员": [], "编剧": []}
    cast_section = soup.select('div.navBar + div img')  # 图片卡片（头像）区域
    if cast_section:
        for img in soup.select('div.sections section img'):
            role = img.find_parent('div').find_previous_sibling("span")
            role_name = role.get_text(strip=True) if role else ""
            alt = img.get("alt", "")
            if "导演" in role_name:
                cast_info["导演"].append(alt)
            elif "编剧" in role_name:
                cast_info["编剧"].append(alt)
            else:
                cast_info["演员"].append(alt)

    # 9. 出品公司等（制作单位）
    companies = {}
    for div in soup.select("div.topboard-panel ~ div.section-group div.section-group section"):
        h2 = div.find('h2') or div.find('p')
        if h2:
            title = h2.get_text(strip=True).replace(':', '')
            companies[title] = [img.get("alt", "") for img in div.select('img') if img.get("alt")]

    # 10. 技术参数
    technical_specs = {}
    spec_section = soup.find('section', class_='technical-section')
    if spec_section:
        for row in spec_section.select('div.info-detail-row'):
            key_tag = row.find('p', class_='info-detail-title')
            val_tag = row.find('p', class_='info-detail-content')
            if key_tag and val_tag:
                technical_specs[key_tag.get_text(strip=True)] = val_tag.get_text(strip=True)

    # 11. 营销事件
    marketing_events = []
    for event in soup.select('section.marketing-section div.trace-item'):
        time_tag = event.select_one('span.date-str')
        title_tag = event.select_one('span.trace-name')
        tag_tag = event.select_one('span.trace-tip em')
        if time_tag and title_tag:
            marketing_events.append({
                "time": time_tag.get_text(strip=True),
                "event": title_tag.get_text(strip=True),
                "tag": tag_tag.get_text(strip=True) if tag_tag else ""
            })

    return {
        "movie_title": movie_title,
        "basic_info": basic_info,
        "rating_info": rating_info,
        "box_office_series": box_office_series,
        "schedule_series": schedule_series,
        "pre_release_wish_series": pre_wish_series,
        "persona_data": persona_data,
        "cast_info": cast_info,
        "companies": companies,
        "technical_specs": technical_specs,
        "marketing_events": marketing_events
    }

def save_to_json(data, filename):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"数据已保存到 {filename}")

if __name__ == "__main__":
    base_url = "https://piaofang.maoyan.com"
    rankings_url = f"{base_url}/rankings/year"

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/115.0.0.0 Safari/537.36"
        )
    }

    os.makedirs(r"D:\project_movie_pred\movie_data", exist_ok=True)

    response = requests.get(rankings_url, headers=headers)
    if response.status_code != 200:
        print(f"获取排行榜页面失败，状态码: {response.status_code}")
        exit()

    soup = BeautifulSoup(response.text, 'html.parser')

    # 提取所有电影链接
    movie_links = []
    for ul in soup.select("div#ranks-list ul.row"):
        href = ul.get("data-com")
        if href and "/movie/" in href:
            match = re.search(r"href:'(/movie/\d+)'", href)
            if match:
                movie_links.append(base_url + match.group(1))

    print(f"一共找到 {len(movie_links)} 部电影")

    for movie_url in tqdm(movie_links, desc="抓取进度"):
        try:
            result = crawl_movie_data(movie_url)
            if result:
                movie_id = movie_url.split("/")[-1]
                save_to_json(result, os.path.join(r"D:\project_movie_pred\movie_data", f"movie_data_{movie_id}.json"))
        except Exception as e:
            print(f"抓取失败: {movie_url}, 错误: {e}")
