#!/usr/bin/env python3
"""Feature checklist module for harness.

Provides utilities for managing the claude-features.json file.
"""

import os
import json
from datetime import datetime
from pathlib import Path

FEATURES_FILE = "claude-features.json"


def get_features_path(work_dir=None):
    """Get path to features file."""
    if work_dir is None:
        work_dir = os.getcwd()
    return Path(work_dir) / FEATURES_FILE


def load_features(work_dir=None):
    """Load features from JSON file."""
    path = get_features_path(work_dir)
    if path.exists():
        with open(path, 'r') as f:
            return json.load(f)
    return {"features": [], "metadata": {}}


def save_features(data, work_dir=None):
    """Save features to JSON file."""
    path = get_features_path(work_dir)
    data['metadata']['last_updated'] = datetime.now().isoformat()
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)


def add_feature(name, description, category=None, priority=None, work_dir=None):
    """Add a new feature to the checklist."""
    data = load_features(work_dir)

    feature = {
        "id": len(data['features']) + 1,
        "name": name,
        "description": description,
        "status": "failing",  # Default to failing per Anthropic's guidance
        "category": category,
        "priority": priority or len(data['features']) + 1,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat()
    }

    data['features'].append(feature)
    save_features(data, work_dir)
    return feature


def update_feature_status(feature_id, status, notes=None, work_dir=None):
    """Update a feature's status."""
    valid_statuses = ['failing', 'in_progress', 'passing']
    if status not in valid_statuses:
        raise ValueError(f"Status must be one of: {valid_statuses}")

    data = load_features(work_dir)

    for feature in data['features']:
        if feature['id'] == feature_id:
            feature['status'] = status
            feature['updated_at'] = datetime.now().isoformat()
            if notes:
                if 'notes' not in feature:
                    feature['notes'] = []
                feature['notes'].append({
                    'timestamp': datetime.now().isoformat(),
                    'content': notes
                })
            break

    save_features(data, work_dir)


def get_next_features(count=5, work_dir=None):
    """Get next priority features to work on."""
    data = load_features(work_dir)

    # Filter to failing and in_progress, sort by priority
    pending = [
        f for f in data['features']
        if f.get('status') in ('failing', 'in_progress')
    ]
    pending.sort(key=lambda x: (
        0 if x.get('status') == 'in_progress' else 1,
        x.get('priority', 999)
    ))

    return pending[:count]


def get_feature_summary(work_dir=None):
    """Get summary statistics of features."""
    data = load_features(work_dir)

    features = data.get('features', [])
    return {
        'total': len(features),
        'passing': sum(1 for f in features if f.get('status') == 'passing'),
        'failing': sum(1 for f in features if f.get('status') == 'failing'),
        'in_progress': sum(1 for f in features if f.get('status') == 'in_progress')
    }


def initialize_features_file(project_name=None, work_dir=None):
    """Initialize a new features file."""
    path = get_features_path(work_dir)

    if path.exists():
        return False  # Already exists

    project = project_name or Path(work_dir or os.getcwd()).name

    data = {
        "metadata": {
            "project": project,
            "created_at": datetime.now().isoformat(),
            "last_updated": datetime.now().isoformat(),
            "description": "Feature checklist for long-running agent workflows"
        },
        "features": []
    }

    save_features(data, work_dir)
    return True


def import_features_from_list(feature_list, work_dir=None):
    """Import multiple features from a list of dicts.

    Each dict should have at minimum 'name' and 'description'.
    Optional: 'category', 'priority'
    """
    data = load_features(work_dir)

    for i, item in enumerate(feature_list):
        feature = {
            "id": len(data['features']) + 1,
            "name": item.get('name', f'Feature {i+1}'),
            "description": item.get('description', ''),
            "status": "failing",
            "category": item.get('category'),
            "priority": item.get('priority', len(data['features']) + 1),
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        data['features'].append(feature)

    save_features(data, work_dir)
    return len(feature_list)
