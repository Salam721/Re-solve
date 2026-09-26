# Requirements: Re-solve

**Problem.** Cyberbullying on social media usually happens in the moment. Most platforms react after harm is done (reports, takedowns).
**Intended users.** Anyone commenting on social media; teens and young adults are the most affected group and our primary demo persona.
**Goal.** Give the writer a "Re-solve" before posting: explain the problem, offer kinder wording, and escalate only when real risk exists.

Severity tiers used below: **none**, **mild** (rude/teasing), **moderate** (targeted insult, harassment, slur), **severe** (threat, encouraging self-harm, doxxing).

---

## R1. Check comments before posting
*As a commenter, I want my comment checked before it goes live, so I don't hurt someone without realizing it.*
1. WHEN a user selects Post THE SYSTEM SHALL analyze the comment before it is published.
2. WHEN the analysis finds no bullying THE SYSTEM SHALL publish the comment without interrupting the user.
3. WHILE a comment is being analyzed THE SYSTEM SHALL show a visible checking state and disable a second submission.
4. IF a comment is empty or longer than 1,000 characters THEN THE SYSTEM SHALL reject it with a clear message.

## R2. Detect bullying, including disguised and context-based language
*As a platform, I want detection that catches obvious and subtle bullying.*
1. WHEN a comment is received THE SYSTEM SHALL normalize disguised spellings (look-alike characters, spaced letters, repeated letters, asterisk masking) before matching.
2. WHEN a comment is received THE SYSTEM SHALL score it with Azure AI Content Safety for hate, violence, sexual, and self-harm content.
3. WHEN a comment is received THE SYSTEM SHALL have a Foundry classifier agent return a category, severity, target, and one-sentence reason.
4. WHEN results disagree THE SYSTEM SHALL use the highest severity from the classifier, the Content Safety floor (level 4+), and the word-bank floor phrases.
5. IF the classifier agent is unavailable THEN THE SYSTEM SHALL fall back to Content Safety and the word bank and mark the result as degraded.

## R3. Warn and suggest alternatives
*As a commenter, I want to understand what's wrong and have an easy kinder option.*
1. WHEN a comment is mild, moderate, or severe THE SYSTEM SHALL show a warning that names the problem in plain language.
2. WHEN a warning is shown THE SYSTEM SHALL show two or three alternative comments that keep the writer's point without the hostility.
3. WHEN the user selects an alternative THE SYSTEM SHALL place it in the comment box for the user to post.
4. WHEN the user selects Edit THE SYSTEM SHALL return focus to the comment box with their text intact.

## R4. Post anyway and escalation by severity
*As a commenter, I keep the final choice for most comments; as a platform, I need a safety net for dangerous ones.*
1. WHEN a comment is mild THE SYSTEM SHALL allow Post anyway without notifying anyone.
2. WHEN a user posts a moderate comment anyway THE SYSTEM SHALL publish it and add it to the moderator queue.
3. WHEN a comment is severe THE SYSTEM SHALL not offer Post anyway, SHALL refuse any attempt to post it, and SHALL alert the moderator queue immediately.
4. WHEN a comment encourages self-harm or the writer appears to be in distress THE SYSTEM SHALL show crisis resources (988 Suicide & Crisis Lifeline, Crisis Text Line, findahelpline.com).
5. WHEN the escalation agent recommends a stronger action than the severity baseline THE SYSTEM SHALL apply the stronger action; THE SYSTEM SHALL never apply a weaker one.
6. IF the posted text differs from the analyzed text THEN THE SYSTEM SHALL require a new analysis.

## R5. Moderator queue
*As a moderator, I want to review escalations with just the information I need.*
1. WHEN a comment is escalated THE SYSTEM SHALL record its masked text, tier, category, reason, and a short moderator summary.
2. WHEN a moderator resolves an item THE SYSTEM SHALL remove it from the open queue.
3. WHEN an item is older than the retention period (default 24 hours) THE SYSTEM SHALL delete it.

## R6. Privacy
1. WHEN a comment contains an email, phone number, or street address THE SYSTEM SHALL mask it before any cloud service or agent sees it.
2. THE SYSTEM SHALL not store comments that were not published or escalated.
3. THE SYSTEM SHALL tell users on the page that comments are checked and why.
4. THE SYSTEM SHALL keep all keys server-side.

## R7. Transparency for the demo
1. WHEN a comment is analyzed THE SYSTEM SHALL show an "Under the hood" trace listing each step, which agent or service ran it, its time, and its output.
2. THE SYSTEM SHALL show whether it is running live on Foundry or in offline backup mode.

## Out of scope
Accounts and login, multi-comment harassment patterns, images, languages other than English, production deployment.

## Known limitations (to state in the demo)
Can misread sarcasm, slang, reclaimed words, and non-English text; judges single comments only; supports human moderators rather than replacing them.
