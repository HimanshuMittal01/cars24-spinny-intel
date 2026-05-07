# src/ci/vision/tools.py
"""Anthropic tool definitions for the outer vision agent."""

LIST_PHOTOS_TOOL = {
    "name": "list_photos",
    "description": "List all photos available for the current listing.",
    "input_schema": {"type": "object", "properties": {}, "required": []},
}

INSPECT_PHOTO_TOOL = {
    "name": "inspect_photo",
    "description": (
        "Inspect a specific photo by index. Returns aspects_visible and per-aspect "
        "findings. Use this to gather evidence before final_assessment."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "idx": {"type": "integer", "description": "Photo index from list_photos."},
        },
        "required": ["idx"],
    },
}

NOTE_EVIDENCE_GAP_TOOL = {
    "name": "note_evidence_gap",
    "description": (
        "Record that you looked but cannot evidence this aspect (e.g. no photo "
        "shows the engine bay). Use ONLY when no available photo evidences the aspect."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "aspect": {
                "type": "string",
                "enum": ["exterior_panels", "interior_cabin",
                         "dashboard_console", "tyres", "engine_bay"],
            },
            "reason": {"type": "string"},
        },
        "required": ["aspect", "reason"],
    },
}

FINAL_ASSESSMENT_TOOL = {
    "name": "final_assessment",
    "description": (
        "Submit your final per-aspect assessment. This terminates the loop. "
        "Include all 5 aspects; use 'not_visible' severity for any aspect with no evidence."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "per_aspect": {
                "type": "object",
                "properties": {
                    a: {
                        "type": "object",
                        "properties": {
                            "severity": {
                                "type": "string",
                                "enum": ["pristine", "light_wear", "moderate",
                                         "heavy", "defect", "not_visible"],
                            },
                            "confidence": {
                                "type": "string", "enum": ["low", "med", "high"],
                            },
                            "photo_refs": {
                                "type": "array", "items": {"type": "integer"},
                            },
                            "evidence_note": {"type": "string", "maxLength": 200},
                        },
                        "required": ["severity", "confidence", "photo_refs", "evidence_note"],
                    }
                    for a in ("exterior_panels", "interior_cabin",
                              "dashboard_console", "tyres", "engine_bay")
                },
                "required": ["exterior_panels", "interior_cabin",
                             "dashboard_console", "tyres", "engine_bay"],
            }
        },
        "required": ["per_aspect"],
    },
}

ALL_TOOLS = [LIST_PHOTOS_TOOL, INSPECT_PHOTO_TOOL,
             NOTE_EVIDENCE_GAP_TOOL, FINAL_ASSESSMENT_TOOL]
