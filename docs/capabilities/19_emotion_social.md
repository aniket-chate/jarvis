# Capability 19: Emotion & Social Context

**Capability ID:** `19_emotion_social`  
**Classification:** `FOUNDATION`  
**Safety Classification:** `READ_ONLY`  
**Domain:** `perception`  
**Primary Provider:** `provider.perception.sentiment`  
**Fallback Provider:** `provider.llm.ollama_local`  

---

## 1. Capability Purpose & Scope
Evaluates conversational sentiment, user mood cues, and situational urgency to adapt response cadence, empathy, and execution priority without claiming false factual certainty about human emotional states.

---

## 2. Supported Operations
- `emotion.analyze_sentiment`: Evaluates probabilistic sentiment polarity (positive, frustrated, neutral) with explicit confidence estimation and tone recommendations.
- `emotion.detect_urgency`: Detects conversational urgency indicators ("immediately", "ASAP", "emergency") to apply priority boosts to critical system actions.

---

## 3. Required Context & World Model State
- **User Utterance:** Raw text string or transcript of user speech.
- **Current Task Context:** Ongoing execution priority.

---

## 4. Provider Implementation & Selection
- **Implementation:** `capabilities/providers/emotion_provider.py` (`EmotionSocialContextProvider`).
- **Fast-Path Latency:** Evaluates in **< 2.0 ms**.

---

## 5. Safety, Verification & Error Handling
- **Safety Policy:** `Level 0: ALLOWED` (Read-only sentiment interpretation).
- **Verification Strategy:** `SENTIMENT_CLASSIFICATION_CHECK` ensures outputs are explicitly marked as probabilistic (`probabilistic_claim: True`) to prevent the assistant from asserting unverifiable emotional facts.
- **Adaptive Tone Matching:** Recommends empathetic/supportive tone when frustration is detected; defaults to concise efficiency when urgency is high.
