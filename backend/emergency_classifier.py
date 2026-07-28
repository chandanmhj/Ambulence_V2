"""
Lightweight vector-space text matcher: maps a free-text emergency description
(e.g. "sharp eye pain and blurry vision") to the closest hospital specialty
category, using TF-IDF vectors + cosine similarity.

Deliberately NOT using a hosted embedding API here - this needs to work
reliably live, mid-demo, without depending on external network calls or a
large model download during `docker build`. TF-IDF is a real vector-space
model (bag-of-words vectors + cosine similarity), just a lighter one than
transformer embeddings - plenty good enough for matching short symptom
phrases against a fixed, curated category list.
"""

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# A handful of example phrases per category - the richer this list, the better
# the matching. Add more phrases here anytime to improve accuracy for terms
# people actually type.
CATEGORY_PHRASES = {
    "cardiology": [
        "chest pain", "heart attack", "cardiac arrest", "irregular heartbeat",
        "tightness in chest", "shortness of breath with chest pain", "palpitations",
        "heart problem", "cardiac emergency", "angina", "heart pain",
    ],
    "orthopedic": [
        "broken bone", "bone fracture", "sprained ankle", "dislocated shoulder",
        "sports injury", "fell and broke arm", "back pain after fall",
        "joint pain", "orthopedic injury", "fracture", "bone injury", "leg injury",
    ],
    "ophthalmology": [
        "eye injury", "eye pain", "blurry vision", "something in my eye",
        "red eye", "eye problem", "vision loss", "chemical in eye", "eye trauma",
        "eye infection", "cannot see properly",
    ],
    "ent": [
        "ear pain", "ear infection", "throat pain", "difficulty swallowing",
        "nose bleed", "hearing loss", "sinus problem", "ear nose throat issue",
        "foreign object in ear", "sore throat", "blocked nose",
    ],
    "neurology": [
        "stroke symptoms", "sudden weakness one side", "severe headache",
        "seizure", "head injury", "loss of consciousness", "slurred speech",
        "numbness in face or arm", "neurological emergency", "fainting",
    ],
    "maternity": [
        "pregnant and in labor", "pregnancy complication", "labor pain",
        "miscarriage", "vaginal bleeding during pregnancy", "obstetric emergency",
        "water broke",
    ],
    "pediatric": [
        "child high fever", "infant not breathing well", "child injury",
        "kid swallowed something", "pediatric emergency", "baby not responsive",
    ],
    "psychiatric": [
        "mental health crisis", "suicidal thoughts", "severe panic attack",
        "psychiatric emergency", "acute anxiety episode",
    ],
    "oncology": [
        "cancer patient emergency", "chemotherapy complication", "tumor related pain",
    ],
    "nephrology_urology": [
        "kidney stone pain", "unable to urinate", "blood in urine",
        "severe abdominal and back pain", "kidney failure symptoms",
    ],
    "pulmonology": [
        "difficulty breathing", "asthma attack", "chronic cough with blood",
        "respiratory distress", "lung problem", "can't breathe",
    ],
    "gastroenterology": [
        "severe stomach pain", "vomiting blood", "abdominal pain",
        "digestive emergency", "liver problem", "stomach ache",
    ],
    "general": [
        "general injury", "accident", "not feeling well", "fever", "cut and bleeding",
        "minor injury", "unspecified emergency", "road accident", "burns",
    ],
}

# Similarity below this means the input didn't meaningfully match any specific
# category (e.g. empty text, gibberish, or something totally unrelated) - fall
# back to "general" instead of returning a low-confidence guess.
CONFIDENCE_FLOOR = 0.15

_vectorizer = None
_category_vectors = None
_category_labels = None


def _build_index():
    global _vectorizer, _category_vectors, _category_labels
    all_phrases = []
    labels = []
    for category, phrases in CATEGORY_PHRASES.items():
        for phrase in phrases:
            all_phrases.append(phrase)
            labels.append(category)

    vectorizer = TfidfVectorizer(ngram_range=(1, 2), stop_words="english")
    vectors = vectorizer.fit_transform(all_phrases)

    _vectorizer = vectorizer
    _category_vectors = vectors
    _category_labels = labels


def classify_emergency_text(text: str, top_k: int = 3):
    """
    Returns a list of (category, confidence) tuples, sorted by confidence
    descending, for the top_k best-matching specialty categories.
    confidence is a cosine similarity score in [0, 1].
    """
    if _vectorizer is None:
        _build_index()

    if not text or not text.strip():
        return [("general", 1.0)]

    query_vec = _vectorizer.transform([text])
    sims = cosine_similarity(query_vec, _category_vectors)[0]

    # Aggregate: take the MAX similarity per category (best matching example
    # phrase), not the average - a single strong phrase match is a stronger
    # signal than diluting the score across every example phrase in that
    # category.
    category_best = {}
    for label, sim in zip(_category_labels, sims):
        if label not in category_best or sim > category_best[label]:
            category_best[label] = float(sim)

    ranked = sorted(category_best.items(), key=lambda x: x[1], reverse=True)

    if ranked[0][1] < CONFIDENCE_FLOOR:
        return [("general", 1.0)]

    return ranked[:top_k]
