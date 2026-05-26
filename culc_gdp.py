import csv
import sys
import os

# Course Credit Mapping (Ordered from most specific to least specific)
CREDIT_MAPPING_ORDERED = [
    ("基礎解析学", 3),
    ("線形代数学", 3),
    ("物理学実験基礎", 2),
    ("物理学実験", 4),
    ("基礎物理学実験", 1.5),
    ("基礎化学実験", 1.5),
    ("基礎地学実験", 1.5),
    ("基礎生物学実験", 1.5),
    ("自然科学実験", 3),
    ("学問への扉", 2),
    ("情報科学基礎", 2),
    ("宇宙地球科学", 2),
    ("人間学の話題", 2),
    ("共生学の話題", 2),
    ("文理融合に向けた数理科学", 2),
    ("スポーツ科学", 1),
    ("力学詳論", 2),
    ("電磁気学詳論", 2),
    ("化学基礎論", 2),
    ("生物学序論", 2),
    ("総合英語", 1.5),
    ("中国語初級", 1.5),
    ("物理学セミナー", 1),
    ("力学演習", 1),
    ("電磁気学演習", 1),
    ("物理学演習", 1),
    ("熱物理学演習", 1),
    ("物理数学演習", 1),
    ("数理物理", 2),
    ("量子力学", 2),
    ("統計力学", 2),
    ("電磁気学", 2),
]

# Grade to Point Mapping
GRADE_MAPPING = {
    "Ｓ": 4.0,
    "Ａ": 3.0,
    "Ｂ": 2.0,
    "Ｃ": 1.0,
    "Ｆ": 0.0,
    "秀": 4.0,
    "優": 3.0,
    "良": 2.0,
    "可": 1.0,
    "不可": 0.0,
    "合": None, # Passed but not counted in GPA usually
    "認": None, # Recognized
}

def get_credits(course_name):
    for key, value in CREDIT_MAPPING_ORDERED:
        if key in course_name:
            return value
    # Default values based on patterns
    if "実験" in course_name:
        return 1.5
    if "演習" in course_name or "演義" in course_name:
        return 1
    return 2.0 # Default to 2 for lectures

def calculate_gdp(dir_path):
    # Find SIRS*.txt file in the specified directory
    file_path = None
    for f in os.listdir(dir_path):
        if f.startswith('SIRS') and f.endswith('.txt'):
            file_path = os.path.join(dir_path, f)
            break
    
    if not file_path:
        print(f"Grade report file (SIRS*.txt) not found in {dir_path}")
        return

    print(f"Reading file: {file_path}")

    categories = {
        "全学共通 (共通/言語/スポーツ/情報)": {"credits": 0, "gp_sum": 0, "gpa_credits": 0},
        "専門基礎 (数学/物理詳論/実験)": {"credits": 0, "gp_sum": 0, "gpa_credits": 0},
        "専門教育 (物理学専攻科目)": {"credits": 0, "gp_sum": 0, "gpa_credits": 0},
    }

    try:
        with open(file_path, mode='r', encoding='cp932', errors='replace') as f:
            reader = csv.reader(f)
            header = next(reader)
            
            # Find column indices
            try:
                col_name = header.index("開講科目名 ")
                col_code = header.index("時間割コード")
                col_grade = header.index("評語")
                col_pass = header.index("合否")
            except ValueError:
                # Fallback if names are slightly different
                col_name = 6
                col_code = 5
                col_grade = 11
                col_pass = 12

            for row in reader:
                if len(row) < 13:
                    continue
                
                name = row[col_name].strip()
                code = row[col_code].strip()
                grade = row[col_grade].strip()
                passed = row[col_pass].strip()

                if passed not in ["合", "合格", "認"]:
                    if grade not in ["Ｆ", "不可"]:
                        continue # Skip if not passed and not F
                
                credits = get_credits(name)
                gp = GRADE_MAPPING.get(grade)

                # Categorization
                is_phy_foundation = False
                phy_foundation_keywords = ["基礎解析学", "線形代数学", "力学詳論", "電磁気学詳論", "自然科学実験"]
                for kw in phy_foundation_keywords:
                    if kw in name:
                        is_phy_foundation = True
                        break

                if code.startswith("04"):
                    cat = "専門教育 (物理学専攻科目)"
                elif is_phy_foundation:
                    cat = "専門基礎 (数学/物理詳論/実験)"
                else:
                    cat = "全学共通 (共通/言語/スポーツ/情報)"

                # Debug
                # print(f"NAME: {name:30} | CODE: {code:8} | CAT: {cat[:10]} | CREDITS: {credits}")

                categories[cat]["credits"] += credits
                if gp is not None:
                    categories[cat]["gp_sum"] += gp * credits
                    categories[cat]["gpa_credits"] += credits

        print("-" * 50)
        print(f"{'Category':<30} | {'Credits':<8} | {'GPA':<5}")
        print("-" * 50)
        
        total_credits = 0
        total_gp_sum = 0
        total_gpa_credits = 0
        
        for cat, data in categories.items():
            gpa = data["gp_sum"] / data["gpa_credits"] if data["gpa_credits"] > 0 else 0
            # Print with English labels to avoid mojibake in some environments
            cat_label = cat.split(" ")[0]
            print(f"{cat_label:<30} | {data['credits']:<8.1f} | {gpa:<5.2f}")
            total_credits += data["credits"]
            total_gp_sum += data["gp_sum"]
            total_gpa_credits += data["gpa_credits"]

        print("-" * 50)
        total_gpa = total_gp_sum / total_gpa_credits if total_gpa_credits > 0 else 0
        print(f"{'Total':<30} | {total_credits:<8.1f} | {total_gpa:<5.2f}")
        
        # Physics GDP (Specialized + Specialized Foundation)
        phy_gp_sum = categories["専門基礎 (数学/物理詳論/実験)"]["gp_sum"] + categories["専門教育 (物理学専攻科目)"]["gp_sum"]
        phy_credits = categories["専門基礎 (数学/物理詳論/実験)"]["gpa_credits"] + categories["専門教育 (物理学専攻科目)"]["gpa_credits"]
        phy_gdp = phy_gp_sum / phy_credits if phy_credits > 0 else 0
        
        print("\n研究室配属用GPA (専門+専門基礎):", round(phy_gdp, 3))
        print("-" * 50)

    except Exception as e:
        print(f"Error processing file: {e}")

if __name__ == "__main__":
    # Use the directory where the script is located
    dir_path = os.path.dirname(os.path.abspath(__file__))
    calculate_gdp(dir_path)
