import pytest
from app.services.self_verification import SelfVerificationEngine, ClaimExtractor, EvidenceComparator, ConfidenceScorer, Claim, Mismatch

def test_extract_years():
    extractor = ClaimExtractor()
    claims = extractor.extract("Năm 1954, trận Điện Biên Phủ diễn ra.")
    year_claims = [c for c in claims if c.claim_type == "year"]
    assert len(year_claims) == 1
    assert year_claims[0].value == "1954"

def test_extract_entities():
    extractor = ClaimExtractor(known_entities={"Điện Biên Phủ"})
    claims = extractor.extract("Năm 1954, trận Điện Biên Phủ diễn ra.")
    entity_claims = [c for c in claims if c.claim_type == "entity" and c.value == "Điện Biên Phủ"]
    assert len(entity_claims) > 0

def test_compare_years():
    claims = [Claim("year", "1954", "năm 1954")]
    evidence = [{"year": 1954, "story": "Trận Điện Biên Phủ"}]
    mismatches = EvidenceComparator.compare(claims, evidence)
    assert len(mismatches) == 0

def test_compare_years_mismatch():
    claims = [Claim("year", "1955", "năm 1955")]
    evidence = [{"year": 1954, "story": "Trận Điện Biên Phủ"}]
    mismatches = EvidenceComparator.compare(claims, evidence)
    assert len(mismatches) == 1
    assert mismatches[0].severity == "critical"

def test_compare_entities():
    claims = [Claim("entity", "Điện Biên Phủ", "Điện Biên Phủ")]
    evidence = [{"year": 1954, "story": "Trận Điện Biên Phủ"}]
    mismatches = EvidenceComparator.compare(claims, evidence)
    assert len(mismatches) == 0

def test_compare_entities_mismatch():
    claims = [Claim("entity", "Hà Nội", "Hà Nội")]
    evidence = [{"year": 1954, "story": "Trận Điện Biên Phủ"}]
    mismatches = EvidenceComparator.compare(claims, evidence)
    assert len(mismatches) == 1
    assert mismatches[0].severity == "warning"

def test_scorer_verified():
    claims = [Claim("year", "1954", "năm 1954")]
    mismatches = []
    evidence = [{"year": 1954, "story": "Trận Điện Biên Phủ"}]
    conf, status = ConfidenceScorer.score(claims, mismatches, evidence)
    assert conf >= 0.85
    assert status == "verified"

def test_scorer_rejected():
    claims = [Claim("year", "1955", "năm 1955")]
    mismatches = [Mismatch(claims[0], "No 1955", "critical"), Mismatch(claims[0], "No 1955", "critical")]
    evidence = [{"year": 1954, "story": "Trận Điện Biên Phủ"}]
    conf, status = ConfidenceScorer.score(claims, mismatches, evidence)
    assert conf < 0.6
    assert status == "rejected"

def test_engine():
    engine = SelfVerificationEngine(known_entities={"Điện Biên Phủ"})
    result = engine.verify(
        "Năm 1954, trận Điện Biên Phủ diễn ra.",
        [{"year": 1954, "story": "Trận Điện Biên Phủ"}]
    )
    assert result.is_verified
    assert result.confidence >= 0.85
    assert len(result.mismatches) == 0

def test_engine_mismatch():
    engine = SelfVerificationEngine(known_entities={"Điện Biên Phủ"})
    result = engine.verify(
        "Năm 1955, trận Điện Biên Phủ diễn ra.",
        [{"year": 1954, "story": "Trận Điện Biên Phủ"}]
    )
    assert not result.is_verified
    assert result.status != "verified"
    assert len(result.mismatches) > 0

def test_engine_verify_and_decide():
    engine = SelfVerificationEngine(known_entities={"Điện Biên Phủ"})
    result = engine.verify_and_decide(
        "Năm 1954, trận Điện Biên Phủ diễn ra.",
        [{"year": 1954, "story": "Trận Điện Biên Phủ"}]
    )
    assert result["is_verified"]
    assert result["status"] == "verified"
    assert not result["should_regenerate"]

import pytest
from app.services.self_verification import SelfVerificationEngine, ClaimExtractor, EvidenceComparator, ConfidenceScorer, Claim, Mismatch, VerificationResult

def test_repr():
    c = Claim("year", "1954", "Năm 1954")
    assert repr(c) == "Claim(year: 1954)"

    m = Mismatch(c, "No year", "critical")
    assert repr(m) == "Mismatch(critical: Claim(year: 1954) vs No year)"

def test_critical_mismatches_property():
    c = Claim("year", "1954", "Năm 1954")
    m1 = Mismatch(c, "a", "critical")
    m2 = Mismatch(c, "b", "warning")
    vr = VerificationResult([], [m1, m2], 0.5, "rejected")
    assert len(vr.critical_mismatches) == 1
    assert vr.critical_mismatches[0].severity == "critical"

def test_bare_year_pattern():
    extractor = ClaimExtractor()
    claims = extractor.extract("Diễn ra trong 1954")
    assert claims[0].claim_type == "year"
    assert claims[0].value == "1954"

def test_evidence_comparator_year_not_int():
    claims = [Claim("year", "abcd", "abcd")]
    evidence = [{"year": 1954, "story": "Trận Điện Biên Phủ"}]
    mismatches = EvidenceComparator.compare(claims, evidence)
    assert len(mismatches) == 0  # Ignore non-int year

def test_scorer_no_claims():
    claims = []
    mismatches = []
    evidence = [{"year": 1954, "story": "Trận Điện Biên Phủ"}]
    conf, status = ConfidenceScorer.score(claims, mismatches, evidence)
    assert conf == 0.5
    assert status == "needs_review"

def test_scorer_warning_penalty():
    claims = [Claim("entity", "abc", "abc")]
    mismatches = [Mismatch(claims[0], "missing", "warning")]
    evidence = [{"year": 1954, "story": "Trận Điện Biên Phủ"}]
    conf, status = ConfidenceScorer.score(claims, mismatches, evidence)
    assert conf == 0.9  # 1.0 - 0.1
    assert status == "verified"

def test_scorer_agreement_bonus():
    claims = [Claim("year", "1954", "năm 1954"), Claim("year", "1955", "năm 1955")]
    mismatches = [Mismatch(claims[1], "No 1955", "critical")] # penalty 0.3
    # conf = 1.0 - 0.3 = 0.7. Bonus for 1954 = 0.05 * 1 = 0.05. Bonus for 1955 = 0. Total = 0.75
    evidence = [{"year": 1954, "story": "a"}, {"year": 1954, "story": "b"}, {"year": 1955, "story": "c"}]
    conf, status = ConfidenceScorer.score(claims, mismatches, evidence)
    assert conf == 0.75
    assert status == "needs_review"

def test_scorer_invalid_year_claim():
    claims = [Claim("year", "abcd", "abcd")]
    mismatches = []
    evidence = [{"year": 1954, "story": "a"}, {"year": 1954, "story": "b"}]
    conf, status = ConfidenceScorer.score(claims, mismatches, evidence)
    assert conf == 1.0

def test_evidence_comparator_year_in_evidence_years_but_not_int():
    claims = [Claim("year", "1954", "năm 1954")]
    evidence = [{"year": "abcd", "story": "Trận Điện Biên Phủ"}]
    mismatches = EvidenceComparator.compare(claims, evidence)
    assert len(mismatches) == 1
    assert mismatches[0].severity == "critical"

def test_evidence_comparator_year_in_evidence_text_fallback():
    claims = [Claim("year", "1954", "năm 1954")]
    evidence = [{"year": 1955, "story": "Trận Điện Biên Phủ diễn ra năm 1954"}]
    mismatches = EvidenceComparator.compare(claims, evidence)
    assert len(mismatches) == 0
