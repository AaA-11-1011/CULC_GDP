import csv
import sys
import os
import json
import unicodedata

# ==============================================================================
# 大阪大学 理学部 物理学科 単位・GDP計算ツール (SIKS/SIRS対応版)
# ==============================================================================

GRADE_MAPPING = {
    "S": 4.0, "A": 3.0, "B": 2.0, "C": 1.0, "F": 0.0,
    "秀": 4.0, "優": 3.0, "良": 2.0, "可": 1.0, "不可": 0.0,
}

def load_config(dir_path):
    config_path = os.path.join(dir_path, "config.json")
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Warning: config.jsonの読み込みに失敗しました ({e})。")
    return None

def normalize(text):
    return unicodedata.normalize("NFKC", str(text)).strip()

def get_credits_sirs(course_name, mapping):
    for key, value in mapping:
        if key in course_name: return value
    if "実験" in course_name: return 1.5
    if any(kw in course_name for kw in ["演習", "演義"]): return 1
    return 2.0

def classify_sirs(name, code, rules):
    # SIRS用のキーワードベース分類 (簡易版)
    if code.startswith("04"): return "専門教育_選択" # デフォルト
    if "基礎解析" in name or "線形代数" in name: return "専門基礎教育科目"
    if "学問への扉" in name: return "教養教育_学問への扉"
    return "自由選択"

def is_mandatory(name, mandatory_list):
    return any(m in name for m in mandatory_list)

def get_pad(text, length):
    count = 0
    for c in text:
        count += 2 if ord(c) > 255 else 1
    return text + " " * max(0, length - count)

def find_col(header, target):
    """ヘッダー内からターゲットの文字列を含む列のインデックスを探す"""
    for i, col in enumerate(header):
        if target in col:
            return i
    raise ValueError(f"列 '{target}' が見つかりませんでした。")

def process_siks(file_path, config):
    reqs = config["requirements"]
    mapping = config.get("siks_category_mapping", {})
    mandatory_list = config.get("mandatory_subjects", [])
    
    results = {cat: {"total": 0, "mandatory": 0, "gp_sum": 0, "gpa_credits": 0} for cat in reqs.keys() if cat != "卒業合計"}
    subject_details = []

    with open(file_path, mode='r', encoding='cp932', errors='replace') as f:
        reader = csv.reader(f)
        # "No." が含まれる行までスキップ
        found_header = False
        for row in reader:
            if not row: continue
            if "No." in row:
                header = [normalize(c) for c in row]
                found_header = True
                break
        
        if not found_header: 
            print("エラー: CSV内に 'No.' 列が見つかりませんでした。ファイル形式を確認してください。")
            return None

        try:
            col_cat_detail = find_col(header, "科目詳細区分")
            col_cat_sub = find_col(header, "科目小区分")
            col_name = find_col(header, "開講科目名")
            col_credits = find_col(header, "単位数")
            col_grade = find_col(header, "評語")
            col_pass = find_col(header, "合否")
        except ValueError as e:
            print(f"エラー: {e}")
            return None

        for row in reader:
            if len(row) < col_pass + 1: continue
            
            try:
                cat_detail = normalize(row[col_cat_detail])
                cat_sub = normalize(row[col_cat_sub])
                name = normalize(row[col_name])
                credits = float(row[col_credits])
                grade = normalize(row[col_grade]).upper()
                passed = normalize(row[col_pass])
            except (ValueError, IndexError):
                continue

            if not grade and not passed: continue

            # カテゴリの決定
            target_cat = "自由選択"
            # 小区分から優先的に検索
            for siks_key, internal_cat in mapping.items():
                if siks_key in cat_sub or siks_key in cat_detail:
                    target_cat = internal_cat
                    break
            
            gp = GRADE_MAPPING.get(grade)
            # GPA計算に含めるか: S, A, B, C, F (秀, 優, 良, 可, 不可) のいずれかの評価がある場合
            is_gpa_subject = grade in ["S", "A", "B", "C", "F", "秀", "優", "良", "可", "不可"]
            
            is_earned = any(kw in passed for kw in ["合", "認", "蜷"]) or (gp is not None and grade not in ["F", "不可"])

            if target_cat not in results: results[target_cat] = {"total": 0, "mandatory": 0, "gp_sum": 0, "gpa_credits": 0}
            
            if is_earned:
                results[target_cat]["total"] += credits
                if is_mandatory(name, mandatory_list):
                    results[target_cat]["mandatory"] += credits
            
            if is_gpa_subject and gp is not None:
                results[target_cat]["gp_sum"] += gp * credits
                results[target_cat]["gpa_credits"] += credits
                subject_details.append(f"{name:30} | {grade:2} | {gp:3.1f} | {credits:3.1f} | {target_cat}")

    return results, subject_details

def calculate_gdp(file_path, config):
    is_siks = "SIKS" in os.path.basename(file_path)
    print(f"Reading ({'SIKS' if is_siks else 'SIRS'}): {os.path.basename(file_path)}\n")
    
    if is_siks:
        res = process_siks(file_path, config)
        if not res:
            print("Error: SIKSファイルの解析に失敗しました。")
            return
        results, subject_details = res
    else:
        # 以前のSIRS処理 (省略)
        print("SIRSファイルは単位数不明のためSIKSファイルの使用を推奨します。")
        return

    reqs = config["requirements"]
    output_lines = []
    def log(text=""):
        print(text)
        output_lines.append(text)

    log("=" * 90)
    log(f"{get_pad('区分', 28)} | {'取得':>5} | {'要件':>5} | {'未得必':>5} | {'不足':>5} | {'GPA':>5}")
    log("-" * 90)
    
    sum_total, sum_mand, sum_gp, sum_gpa_c = 0, 0, 0, 0
    display_order = [c for c in reqs.keys() if c != "卒業合計"]
    excess_credits = 0

    for cat in display_order:
        if cat == "自由選択": continue
        d = results.get(cat, {"total": 0, "mandatory": 0, "gp_sum": 0, "gpa_credits": 0})
        gpa = d["gp_sum"] / d["gpa_credits"] if d["gpa_credits"] > 0 else 0
        r = reqs.get(cat, {"total": 0, "mandatory": 0})
        unearned_mand = max(0, r["mandatory"] - d["mandatory"])
        shortage = max(0, r["total"] - d["total"] - unearned_mand)
        if d["total"] > r["total"]: excess_credits += (d["total"] - r["total"])
        log(f"{get_pad(cat, 28)} | {d['total']:>5.1f} | {r['total']:>5.1f} | {unearned_mand:>5.1f} | {shortage:>5.1f} | {gpa:>5.2f}")
        sum_total += d["total"]
        sum_mand += d["mandatory"]
        sum_gp += d["gp_sum"]
        sum_gpa_c += d["gpa_credits"]

    free_cat = "自由選択"
    d = results.get(free_cat, {"total": 0, "mandatory": 0, "gp_sum": 0, "gpa_credits": 0})
    total_free_earned = d["total"] + excess_credits
    req_free = reqs.get(free_cat, {"total": 8.0})["total"]
    short_free = max(0, req_free - total_free_earned)
    gpa_free = d["gp_sum"] / d["gpa_credits"] if d["gpa_credits"] > 0 else 0
    log(f"{get_pad(free_cat, 28)} | {total_free_earned:>5.1f} | {req_free:>5.1f} | {0.0:>5.1f} | {short_free:>5.1f} | {gpa_free:>5.2f}")
    
    log("-" * 90)
    total_gpa = sum_gp / sum_gpa_c if sum_gpa_c > 0 else 0
    final_req = reqs["卒業合計"]
    total_unearned_mand = sum(max(0, reqs[c].get("mandatory", 0) - results.get(c, {"mandatory":0})["mandatory"]) for c in display_order if c != "自由選択")
    log(f"{get_pad('合計', 28)} | {sum_total:>5.1f} | {final_req['total']:>5.1f} | {total_unearned_mand:>5.1f} | {max(0, final_req['total'] - sum_total - total_unearned_mand):>5.1f} | {total_gpa:>5.2f}")
    log("=" * 90)
    
    phy_cats = [c for c in results.keys() if "専門" in c]
    phy_gp = sum(results[c]["gp_sum"] for c in phy_cats)
    phy_c = sum(results[c]["gpa_credits"] for c in phy_cats)
    log(f"\n【参考】研究室配属用GPA (専門基礎＋専門教育): {round(phy_gp / phy_c, 3) if phy_c > 0 else 0}")

    with open(os.path.join(os.path.dirname(file_path), "gdp_result.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(output_lines))
    with open(os.path.join(os.path.dirname(file_path), "debug_subjects.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(subject_details))

if __name__ == "__main__":
    try:
        # 実行ファイルのディレクトリを取得
        if getattr(sys, 'frozen', False):
            # .exeで実行されている場合
            base_dir = os.path.dirname(sys.executable)
        else:
            # .pyで実行されている場合
            base_dir = os.path.dirname(os.path.abspath(__file__))

        config = load_config(base_dir)
        if config:
            # SIKSを優先的に検索
            target_file = next((os.path.join(base_dir, f) for f in os.listdir(base_dir) if f.startswith('SIKS') and f.endswith('.csv')), None)
            if not target_file:
                target_file = next((os.path.join(base_dir, f) for f in os.listdir(base_dir) if f.startswith('SIRS') and (f.endswith('.txt') or f.endswith('.csv'))), None)
            
            if target_file:
                calculate_gdp(target_file, config)
            else:
                print(f"エラー: フォルダ {base_dir} 内に SIKS*.csv または SIRS*.txt が見つかりません。")
                print("KOANからダウンロードしたファイルをこのプログラムと同じ場所に置いてください。")
        else:
            print("エラー: config.json が見つかりません。")
            
    except Exception as e:
        import traceback
        print("\n" + "!"*50)
        print("予期しないエラーが発生しました:")
        print(f"Error: {e}")
        print("-" * 50)
        traceback.print_exc()
        print("!"*50)
    
    finally:
        print("\n" + "="*30)
        input("処理が完了（または中断）しました。エンターキーを押すと終了します...")
