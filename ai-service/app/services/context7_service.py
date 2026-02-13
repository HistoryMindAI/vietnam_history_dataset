"""
Context7 Integration Service

Sử dụng Context7 để cải thiện độ chính xác của câu trả lời
bằng cách lọc và xếp hạng các sự kiện dựa trên ngữ cảnh câu hỏi.
"""
import re
from typing import List, Dict, Any


def extract_query_focus(query: str) -> Dict[str, Any]:
    """
    Phân tích câu hỏi để xác định trọng tâm và yêu cầu cụ thể.
    
    Returns:
        Dict chứa:
        - main_topics: Các chủ đề chính (triều đại, nhân vật, sự kiện)
        - required_keywords: Từ khóa bắt buộc phải có trong câu trả lời
        - required_persons: Nhân vật bắt buộc phải có
        - excluded_keywords: Từ khóa cần loại trừ
        - question_type: Loại câu hỏi (kể, liệt kê, so sánh, v.v.)
    """
    query_lower = query.lower()
    
    # Xác định loại câu hỏi
    question_type = "general"
    if any(word in query_lower for word in ["kể", "kể cho", "nói về", "giới thiệu"]):
        question_type = "narrative"
    elif any(word in query_lower for word in ["liệt kê", "kể tên", "có những", "có bao nhiêu"]):
        question_type = "list"
    elif any(word in query_lower for word in ["so sánh", "khác nhau", "giống nhau"]):
        question_type = "compare"
    elif any(word in query_lower for word in ["tại sao", "vì sao", "nguyên nhân"]):
        question_type = "why"
    elif any(word in query_lower for word in ["như thế nào", "thế nào", "ra sao"]):
        question_type = "how"
    elif any(word in query_lower for word in ["ai là", "là ai"]):
        question_type = "who"
    
    # Trích xuất chủ đề chính
    main_topics = []
    
    # Triều đại
    dynasty_patterns = [
        r"triều đại\s+(\w+)",
        r"nhà\s+(\w+)",
        r"triều\s+(\w+)",
        r"thời\s+(\w+)",
    ]
    for pattern in dynasty_patterns:
        matches = re.findall(pattern, query_lower)
        main_topics.extend([f"dynasty:{m}" for m in matches])
    
    # Nhân vật - ĐỘNG, lấy từ PERSON_ALIASES và PERSONS_INDEX
    required_persons = []
    
    try:
        import app.core.startup as startup
        
        # Lấy tất cả tên nhân vật từ PERSON_ALIASES (bao gồm cả aliases và canonical)
        all_person_names = set()
        if hasattr(startup, 'PERSON_ALIASES') and startup.PERSON_ALIASES:
            # Thêm tất cả aliases
            all_person_names.update(startup.PERSON_ALIASES.keys())
            # Thêm tất cả canonical names
            all_person_names.update(startup.PERSON_ALIASES.values())
        
        # Thêm từ PERSONS_INDEX
        if hasattr(startup, 'PERSONS_INDEX') and startup.PERSONS_INDEX:
            all_person_names.update(startup.PERSONS_INDEX.keys())
        
        # Sắp xếp theo độ dài giảm dần để tránh match substring
        # Ví dụ: "Trần Hưng Đạo" phải được check trước "Trần"
        sorted_persons = sorted(all_person_names, key=len, reverse=True)
        
        # Tìm nhân vật trong query
        for person in sorted_persons:
            if person and person in query_lower:
                main_topics.append(f"person:{person}")
                required_persons.append(person)
    except (ImportError, AttributeError):
        # Fallback: nếu không có startup data, dùng pattern matching cơ bản
        # Tìm các cụm từ có dạng tên người (chữ hoa đầu từ)
        # Pattern: 2-3 từ viết hoa liên tiếp
        name_pattern = r'\b([A-ZÀÁẠẢÃÂẦẤẬẨẪĂẰẮẶẲẴÈÉẸẺẼÊỀẾỆỂỄÌÍỊỈĨÒÓỌỎÕÔỒỐỘỔỖƠỜỚỢỞỠÙÚỤỦŨƯỪỨỰỬỮỲÝỴỶỸĐ][a-zàáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]+(?:\s+[A-ZÀÁẠẢÃÂẦẤẬẨẪĂẰẮẶẲẴÈÉẸẺẼÊỀẾỆỂỄÌÍỊỈĨÒÓỌỎÕÔỒỐỘỔỖƠỜỚỢỞỠÙÚỤỦŨƯỪỨỰỬỮỲÝỴỶỸĐ][a-zàáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]+){1,2})\b'
        matches = re.findall(name_pattern, query)
        for match in matches:
            person_lower = match.lower()
            main_topics.append(f"person:{person_lower}")
            required_persons.append(person_lower)
    
    # Sự kiện/chủ đề
    event_patterns = [
        (r"chiến công", "military_achievement"),
        (r"kháng chiến", "resistance"),
        (r"chống\s+(\w+)", "against"),
        (r"đánh\s+(\w+)", "battle"),
        (r"khởi nghĩa", "uprising"),
        (r"cách mạng", "revolution"),
    ]
    for pattern, event_type in event_patterns:
        if re.search(pattern, query_lower):
            main_topics.append(f"event:{event_type}")
    
    # Từ khóa bắt buộc - những từ quan trọng trong câu hỏi
    required_keywords = []
    
    # Nếu hỏi về "chiến công chống X" thì phải có từ khóa liên quan đến chiến tranh
    if "chiến công" in query_lower or "chiến thắng" in query_lower:
        required_keywords.extend(["chiến", "đánh", "thắng", "kháng", "quân"])
    
    # Nếu hỏi về "chống X" thì phải có X trong kết quả
    against_match = re.search(r"chống\s+([\w\s]+?)(?:\s+và|\s*$|[,.])", query_lower)
    if against_match:
        enemy = against_match.group(1).strip()
        required_keywords.append(enemy)
    
    # Nếu hỏi về triều đại cụ thể, phải có tên triều đại
    for pattern in dynasty_patterns:
        matches = re.findall(pattern, query_lower)
        if matches:
            required_keywords.extend(matches)
    
    # ĐỘNG: Trích xuất các từ khóa quan trọng từ câu hỏi
    # Tìm các cụm từ riêng (proper nouns) - thường là tên địa danh, quốc hiệu
    # Pattern: Từ viết hoa + từ thường (ví dụ: "Đại Việt", "Đại La")
    proper_noun_pattern = r'\b([A-ZÀÁẠẢÃÂẦẤẬẨẪĂẰẮẶẲẴÈÉẸẺẼÊỀẾỆỂỄÌÍỊỈĨÒÓỌỎÕÔỒỐỘỔỖƠỜỚỢỞỠÙÚỤỦŨƯỪỨỰỬỮỲÝỴỶỸĐ][a-zàáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]+(?:\s+[A-ZÀÁẠẢÃÂẦẤẬẨẪĂẰẮẶẲẴÈÉẸẺẼÊỀẾỆỂỄÌÍỊỈĨÒÓỌỎÕÔỒỐỘỔỖƠỜỚỢỞỠÙÚỤỦŨƯỪỨỰỬỮỲÝỴỶỸĐ][a-zàáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]+)*)\b'
    proper_nouns = re.findall(proper_noun_pattern, query)
    
    # Lọc bỏ các từ phổ biến không phải từ khóa quan trọng
    common_words = {"hãy", "cho", "tôi", "biết", "về", "như", "thế", "nào", "ra", "sao"}
    for noun in proper_nouns:
        noun_lower = noun.lower()
        # Chỉ thêm nếu không phải từ phổ biến và chưa có trong required_keywords
        if noun_lower not in common_words and noun_lower not in required_keywords:
            # Kiểm tra xem có phải là tên nhân vật không (đã xử lý ở trên)
            if noun_lower not in required_persons:
                required_keywords.append(noun_lower)
    
    return {
        "main_topics": main_topics,
        "required_keywords": required_keywords,
        "required_persons": required_persons,
        "excluded_keywords": [],
        "question_type": question_type,
    }


def calculate_relevance_score(event: Dict[str, Any], query_focus: Dict[str, Any], query: str) -> float:
    """
    Tính điểm liên quan của một sự kiện với câu hỏi dựa trên Context7.
    
    Điểm càng cao = càng liên quan đến câu hỏi.
    
    IMPROVED: Tăng cường khả năng hiểu câu hỏi linh hoạt hơn với:
    - Fuzzy matching cho từ khóa
    - Synonym matching
    - Partial matching
    """
    score = 0.0
    query_lower = query.lower()
    
    # Lấy thông tin sự kiện
    story = (event.get("story", "") or event.get("event", "")).lower()
    title = (event.get("title", "") or "").lower()
    dynasty = (event.get("dynasty", "") or "").lower()
    keywords = [k.lower() for k in event.get("keywords", [])]
    persons = [p.lower() for p in (event.get("persons", []) or [])]
    persons_all = [p.lower() for p in (event.get("persons_all", []) or [])]
    all_persons = list(set(persons + persons_all))
    places = [p.lower() for p in event.get("places", [])]
    
    # Kết hợp tất cả text để tìm kiếm
    all_text = f"{story} {title} {dynasty} {' '.join(keywords)} {' '.join(all_persons)} {' '.join(places)}"
    
    # Helper function: fuzzy match với threshold
    def fuzzy_contains(text: str, keyword: str, threshold: float = 0.8) -> bool:
        """Kiểm tra xem keyword có xuất hiện trong text (cho phép sai sót nhỏ)"""
        if keyword in text:
            return True
        
        # SPECIAL CASE: Phân biệt "Nguyên" (Nguyên Mông) và "Nguyễn" (họ người Việt)
        # Không cho phép fuzzy match giữa 2 từ này
        if keyword in ["nguyên", "nguyên mông", "mông nguyên"] and "nguyễn" in text:
            return False
        if keyword in ["nguyễn"] and "nguyên" in text:
            return False
        
        # Tách từ và kiểm tra từng từ
        text_words = text.split()
        keyword_words = keyword.split()
        
        # Nếu keyword là 1 từ, check fuzzy với mỗi từ trong text
        if len(keyword_words) == 1:
            from difflib import SequenceMatcher
            for word in text_words:
                if len(word) >= 3 and len(keyword) >= 3:
                    # SPECIAL CASE: Không fuzzy match "nguyên" với "nguyễn"
                    if (keyword.lower() == "nguyên" and word.lower() == "nguyễn") or \
                       (keyword.lower() == "nguyễn" and word.lower() == "nguyên"):
                        continue
                    
                    ratio = SequenceMatcher(None, word, keyword).ratio()
                    if ratio >= threshold:
                        return True
        # Nếu keyword là nhiều từ, check substring với threshold thấp hơn
        else:
            from difflib import SequenceMatcher
            keyword_str = " ".join(keyword_words)
            # Tạo các n-gram từ text
            for i in range(len(text_words) - len(keyword_words) + 1):
                text_ngram = " ".join(text_words[i:i+len(keyword_words)])
                ratio = SequenceMatcher(None, text_ngram, keyword_str).ratio()
                if ratio >= threshold:
                    return True
        return False
    
    # 0a. KIỂM TRA NHÂN VẬT - nếu câu hỏi chỉ định nhân vật cụ thể
    # thì sự kiện PHẢI liên quan đến nhân vật đó
    required_persons = query_focus.get("required_persons", [])
    if required_persons:
        # Kiểm tra xem sự kiện có liên quan đến nhân vật được hỏi không
        person_match = False
        for required_person in required_persons:
            # Chuẩn hóa tên nhân vật
            required_person_normalized = required_person.strip().lower()
            
            # Kiểm tra trong persons và persons_all với fuzzy matching
            if any(fuzzy_contains(p, required_person_normalized, 0.85) for p in all_persons):
                person_match = True
                break
            
            # Kiểm tra trong story/title với fuzzy matching
            if fuzzy_contains(all_text, required_person_normalized, 0.85):
                person_match = True
                break
            
            # Xử lý các trường hợp đặc biệt
            # "Hai Bà Trưng" có thể xuất hiện dưới dạng "Trưng Trắc", "Trưng Nhị"
            if "hai bà trưng" in required_person_normalized or "trưng" in required_person_normalized:
                if any("trưng" in p for p in all_persons) or "trưng" in all_text:
                    person_match = True
                    break
        
        if not person_match:
            # Nếu câu hỏi về nhân vật X nhưng sự kiện không liên quan đến X
            # -> loại bỏ hoàn toàn
            return 0.001
    
    # 0b. Kiểm tra triều đại - nếu câu hỏi chỉ định triều đại cụ thể
    # thì sự kiện PHẢI thuộc triều đại đó
    query_dynasty = None
    for pattern in [r"nhà\s+(\w+)", r"triều\s+(\w+)", r"thời\s+(\w+)"]:
        match = re.search(pattern, query_lower)
        if match:
            query_dynasty = match.group(1)
            break
    
    if query_dynasty:
        # Fuzzy match cho triều đại
        if not fuzzy_contains(dynasty, query_dynasty, 0.85):
            # Penalty rất lớn - gần như loại bỏ
            return 0.01
    
    # 1. Kiểm tra từ khóa bắt buộc (trọng số cao nhất) - với fuzzy matching
    required_keywords = query_focus.get("required_keywords", [])
    if required_keywords:
        matched_required = 0
        for kw in required_keywords:
            # Xử lý các biến thể của từ khóa
            if kw in ["nguyên", "mông", "nguyên mông", "mông cổ"]:
                # Kiểm tra các biến thể với fuzzy matching
                if any(fuzzy_contains(all_text, variant, 0.8) for variant in ["nguyên", "mông", "nguyên mông", "mông cổ"]):
                    matched_required += 1
            elif fuzzy_contains(all_text, kw, 0.85):
                matched_required += 1
        
        # Nếu có từ khóa bắt buộc nhưng không match được -> loại bỏ
        if required_keywords and matched_required == 0:
            # Không có từ khóa bắt buộc nào -> điểm rất thấp
            return 0.1
        
        # Tính điểm dựa trên tỷ lệ match
        match_ratio = matched_required / len(required_keywords)
        
        # SPECIAL CASE: Preparation/mobilization events
        # Events like "Hịch tướng sĩ" are preparation for war, not direct battles
        # They may not mention the enemy name but are still relevant
        is_preparation_event = any(fuzzy_contains(all_text, kw, 0.8) for kw in ["hịch", "chuẩn bị", "khích lệ", "động viên", "huy động"])
        
        if is_preparation_event:
            # More lenient threshold for preparation events
            if match_ratio < 0.3:
                # Need at least 30% match for preparation events
                return 0.5
        else:
            # Normal threshold for direct battle events
            if match_ratio < 0.5:
                # Match dưới 50% -> điểm thấp
                return 0.5
        
        score += matched_required * 15.0  # Tăng trọng số từ 10 lên 15
    
    # 2. Kiểm tra chủ đề chính - với fuzzy matching
    main_topics = query_focus.get("main_topics", [])
    for topic in main_topics:
        topic_type, topic_value = topic.split(":", 1) if ":" in topic else ("", topic)
        
        if topic_type == "dynasty":
            if fuzzy_contains(dynasty, topic_value, 0.85):
                score += 10.0  # Tăng từ 8.0
        elif topic_type == "person":
            # Kiểm tra nhân vật với fuzzy matching
            if any(fuzzy_contains(p, topic_value, 0.85) for p in all_persons) or fuzzy_contains(all_text, topic_value, 0.85):
                score += 15.0  # Tăng trọng số cho nhân vật
        elif topic_type == "event":
            # Kiểm tra loại sự kiện
            if topic_value == "military_achievement":
                military_keywords = ["chiến", "đánh", "thắng", "kháng", "quân", "trận", "hịch"]
                if any(fuzzy_contains(all_text, kw, 0.8) for kw in military_keywords):
                    score += 12.0  # Tăng từ 6.0
                else:
                    # Nếu hỏi về chiến công mà không có từ khóa quân sự -> penalty nhẹ hơn
                    score -= 5.0  # Giảm từ -10.0
            elif topic_value == "resistance":
                if fuzzy_contains(all_text, "kháng", 0.8) or fuzzy_contains(all_text, "chống", 0.8):
                    score += 12.0  # Tăng từ 6.0
                else:
                    score -= 5.0  # Giảm từ -10.0
            elif topic_value == "against":
                # Nếu hỏi "chống X" thì phải có từ "chống" hoặc liên quan đến chiến tranh
                if fuzzy_contains(all_text, "chống", 0.8) or any(fuzzy_contains(all_text, kw, 0.8) for kw in ["đánh", "kháng", "chiến", "hịch"]):
                    score += 12.0
                else:
                    score -= 5.0  # Giảm từ -10.0
            elif topic_value == "uprising":
                if fuzzy_contains(all_text, "khởi nghĩa", 0.85):
                    score += 12.0
    
    # 3. Đếm số từ khóa từ câu hỏi xuất hiện trong sự kiện - với fuzzy matching
    # Loại bỏ stop words
    stop_words = {"là", "gì", "của", "và", "hay", "có", "cho", "về", "trong", 
                  "hãy", "kể", "tôi", "bạn", "những", "các", "một", "nhà", "triều", "ai"}
    query_words = [w for w in query_lower.split() if len(w) > 2 and w not in stop_words]
    
    matched_words = sum(1 for word in query_words if fuzzy_contains(all_text, word, 0.85))
    score += matched_words * 2.0  # Mỗi từ khớp = +2 điểm
    
    # 4. Bonus cho sự kiện có tone phù hợp
    question_type = query_focus.get("question_type", "general")
    tone = event.get("tone", "")
    
    if question_type == "narrative" and tone == "heroic":
        score += 5.0  # Tăng từ 3.0
    
    # 5. Penalty cho sự kiện quá ngắn (có thể là metadata)
    if len(story) < 30:
        score *= 0.3  # Giảm từ 0.5
    
    # 6. Penalty cho sự kiện không phải heroic khi hỏi về chiến công
    if "chiến công" in query_lower or "chiến thắng" in query_lower:
        if tone != "heroic":
            score *= 0.2  # Giảm mạnh hơn từ 0.3
    
    # 7. Bonus lớn cho sự kiện có từ "chiến thắng" hoặc "đánh bại" khi hỏi về chiến thắng
    if "chiến thắng" in query_lower or "chiến công" in query_lower:
        victory_keywords = ["chiến thắng", "đánh bại", "thắng lợi", "đại phá", "tiêu diệt", "đánh tan"]
        if any(fuzzy_contains(all_text, kw, 0.85) for kw in victory_keywords):
            score += 15.0
    
    # 8. Bonus cho preparation/mobilization events khi hỏi về chiến công
    if "chiến công" in query_lower or "kháng chiến" in query_lower or "chống" in query_lower:
        preparation_keywords = ["hịch", "chuẩn bị", "khích lệ", "động viên", "huy động"]
        if any(fuzzy_contains(all_text, kw, 0.8) for kw in preparation_keywords):
            # Bonus for preparation events - they are part of the war effort
            score += 10.0
    
    return score


def filter_and_rank_events(events: List[Dict[str, Any]], query: str, max_results: int = 10) -> List[Dict[str, Any]]:
    """
    Lọc và xếp hạng các sự kiện dựa trên độ liên quan với câu hỏi.
    
    Sử dụng Context7 để đảm bảo câu trả lời bám sát câu hỏi.
    
    IMPROVED: Xử lý các trường hợp đặc biệt:
    - Query chỉ có năm (ví dụ: "năm 1911") → không lọc chặt
    - Query year range (ví dụ: "từ 40 đến 2025") → không lọc chặt
    - Query đơn giản → threshold thấp hơn
    - Query phức tạp → threshold cao
    """
    if not events:
        return []
    
    # Phân tích câu hỏi
    query_focus = extract_query_focus(query)
    
    # Kiểm tra xem query có phức tạp không
    query_lower = query.lower()
    
    # Query đơn giản: chỉ có năm, không có yêu cầu cụ thể
    is_simple_year_query = bool(re.match(r'^(năm|year)?\s*\d{3,4}\s*(có|gì|sự kiện)?$', query_lower.strip()))
    
    # Query đơn giản: chỉ hỏi về triều đại, không có yêu cầu cụ thể
    is_simple_dynasty_query = bool(re.match(r'^(nhà|triều|thời)\s+\w+\s*(có|gì|sự kiện)?$', query_lower.strip()))
    
    # Query year range: "từ năm X đến năm Y" - nhiều patterns
    is_year_range_query = bool(
        re.search(r'(từ|from|between|giai\s*đoạn).*(đến|to|and|[-–—])', query_lower) or
        re.search(r'\d{1,4}\s*[-–—]\s*\d{1,4}', query_lower)  # "40-2025"
    )
    
    # Nếu là query đơn giản hoặc year range, không áp dụng lọc chặt
    if is_simple_year_query or is_simple_dynasty_query or is_year_range_query:
        # Chỉ sắp xếp theo điểm, không lọc
        scored_events = []
        for event in events:
            score = calculate_relevance_score(event, query_focus, query)
            scored_events.append((score, event))
        
        # Sắp xếp theo điểm giảm dần
        scored_events.sort(key=lambda x: x[0], reverse=True)
        
        # Trả về tất cả events (không lọc theo threshold)
        return [event for score, event in scored_events[:max_results]]
    
    # Query phức tạp: áp dụng lọc chặt như bình thường
    # Tính điểm cho mỗi sự kiện
    scored_events = []
    for event in events:
        score = calculate_relevance_score(event, query_focus, query)
        scored_events.append((score, event))
    
    # Sắp xếp theo điểm giảm dần
    scored_events.sort(key=lambda x: x[0], reverse=True)
    
    # Lọc các sự kiện có điểm quá thấp
    # Giảm threshold để không loại bỏ quá nhiều events liên quan
    min_score_threshold = 5.0  # Giảm từ 10.0 xuống 5.0 để bao gồm nhiều events hơn
    filtered_events = [(score, event) for score, event in scored_events if score >= min_score_threshold]
    
    # Nếu không có sự kiện nào đạt ngưỡng, lấy top 3 sự kiện có điểm cao nhất
    # NHƯNG chỉ nếu điểm của chúng > 0
    if not filtered_events and scored_events:
        top_events = [(score, event) for score, event in scored_events[:3] if score > 0]
        filtered_events = top_events
    
    # Trả về tối đa max_results sự kiện
    return [event for score, event in filtered_events[:max_results]]


def validate_answer_relevance(answer: str, query: str) -> Dict[str, Any]:
    """
    Kiểm tra xem câu trả lời có bám sát câu hỏi không.
    
    Returns:
        Dict chứa:
        - is_relevant: True/False
        - issues: Danh sách các vấn đề phát hiện
        - suggestions: Gợi ý cải thiện
    """
    issues = []
    suggestions = []
    
    query_lower = query.lower()
    answer_lower = answer.lower() if answer else ""
    
    # Kiểm tra 1: Câu hỏi về X nhưng câu trả lời không nhắc đến X
    # Ví dụ: Hỏi về "nhà Trần" nhưng trả lời về "nhà Lý"
    
    # Trích xuất triều đại từ câu hỏi
    dynasty_in_query = None
    for pattern in [r"nhà\s+(\w+)", r"triều\s+(\w+)", r"thời\s+(\w+)"]:
        match = re.search(pattern, query_lower)
        if match:
            dynasty_in_query = match.group(1)
            break
    
    if dynasty_in_query and answer_lower:
        # Kiểm tra xem triều đại có xuất hiện trong câu trả lời không
        # Nhưng cho phép một số trường hợp đặc biệt:
        # - Nếu câu trả lời có nội dung quân sự và câu hỏi về chiến công -> OK
        # - Nếu câu trả lời ngắn và chỉ liệt kê sự kiện -> có thể không nhắc triều đại
        
        has_dynasty_mention = dynasty_in_query in answer_lower
        
        # Nếu không nhắc triều đại, kiểm tra các trường hợp ngoại lệ
        if not has_dynasty_mention:
            # Trường hợp 1: Câu hỏi về chiến công và câu trả lời có nội dung quân sự
            is_military_query = any(kw in query_lower for kw in ["chiến công", "chiến thắng", "kháng chiến"])
            has_military_content = any(kw in answer_lower for kw in ["chiến", "đánh", "thắng", "kháng", "quân", "trận"])
            
            if is_military_query and has_military_content:
                # OK - câu trả lời về chiến công không nhất thiết phải nhắc tên triều đại
                pass
            else:
                issues.append(f"Câu hỏi về '{dynasty_in_query}' nhưng câu trả lời không nhắc đến")
                suggestions.append(f"Chỉ nên trả lời về các sự kiện liên quan đến {dynasty_in_query}")
    
    # Kiểm tra 2: Câu hỏi về "chống X" nhưng câu trả lời không nhắc đến X
    against_match = re.search(r"chống\s+([\w\s]+?)(?:\s+và|\s*$|[,.])", query_lower)
    if against_match and answer_lower:
        enemy = against_match.group(1).strip()
        # Chuẩn hóa tên kẻ thù
        enemy_variants = [enemy]
        if "nguyên mông" in enemy or "mông" in enemy or "nguyên" in enemy:
            enemy_variants = ["nguyên", "mông", "nguyên mông", "mông cổ", "mông-nguyên", "mông-cổ"]
        
        # Kiểm tra xem có ít nhất một biến thể xuất hiện không
        has_enemy = any(variant in answer_lower for variant in enemy_variants)
        if not has_enemy:
            issues.append(f"Câu hỏi về 'chống {enemy}' nhưng câu trả lời không nhắc đến")
            suggestions.append(f"Chỉ nên trả lời về các sự kiện liên quan đến {enemy}")
    
    # Kiểm tra 3: Câu hỏi về "chiến công" nhưng câu trả lời không có nội dung quân sự
    if "chiến công" in query_lower or "chiến thắng" in query_lower:
        military_keywords = ["chiến", "đánh", "thắng", "kháng", "quân", "trận"]
        if answer_lower and not any(kw in answer_lower for kw in military_keywords):
            issues.append("Câu hỏi về chiến công nhưng câu trả lời thiếu nội dung quân sự")
            suggestions.append("Nên tập trung vào các trận chiến và chiến thắng")
    
    is_relevant = len(issues) == 0
    
    return {
        "is_relevant": is_relevant,
        "issues": issues,
        "suggestions": suggestions,
    }
