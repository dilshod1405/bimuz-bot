"""
Centralized role-based permissions for bimuz-bot.

Goal: keep RBAC rules in one place (easy to scale/maintain),
similar to bimuz-dashboard/src/lib/permissions.ts.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional


# Role hierarchy (higher = more privilege)
ROLE_LEVEL = {
    "sotuv_agenti": 0,
    "mentor": 0,
    "assistent": 0,
    "buxgalter": 1,
    "administrator": 2,
    "direktor": 3,
    "dasturchi": 4,
}


def get_role_level(role: Optional[str]) -> int:
    if not role:
        return 0
    return ROLE_LEVEL.get(role, 0)


# ---- Employees (Xodimlar) permissions ----

def can_view_employees(_user_role: Optional[str]) -> bool:
    """Botda Xodimlar bo'limini ko'rish (read) — barcha autentifikatsiyadan o'tgan xodimlar uchun."""
    return True


def can_create_employee(user_role: Optional[str]) -> bool:
    """Create employee: Dasturchi, Direktor, Administrator."""
    return get_role_level(user_role) >= ROLE_LEVEL["administrator"]


def can_update_employee(user_role: Optional[str], target_role: Optional[str]) -> bool:
    """
    Update employee rules (same spirit as dashboard):
    - Dasturchi: everyone
    - Direktor: everyone except Dasturchi
    - Administrator: only roles below Administrator
    - Others: no
    """
    user_level = get_role_level(user_role)
    target_level = get_role_level(target_role)

    if user_level == ROLE_LEVEL["dasturchi"]:
        return True
    if user_level == ROLE_LEVEL["direktor"]:
        return target_level != ROLE_LEVEL["dasturchi"]
    if user_level == ROLE_LEVEL["administrator"]:
        return target_level < ROLE_LEVEL["administrator"]
    return False


def can_delete_employee(user_role: Optional[str], target_role: Optional[str]) -> bool:
    return can_update_employee(user_role, target_role)


def can_assign_role(user_role: Optional[str], target_role: str) -> bool:
    """Can user assign target_role when creating/editing an employee."""
    user_level = get_role_level(user_role)
    target_level = get_role_level(target_role)

    if user_level == ROLE_LEVEL["dasturchi"]:
        return True
    if user_level == ROLE_LEVEL["direktor"]:
        return target_level != ROLE_LEVEL["dasturchi"]
    if user_level == ROLE_LEVEL["administrator"]:
        return target_level < ROLE_LEVEL["administrator"]
    return False


def get_assignable_roles(user_role: Optional[str]) -> List[str]:
    all_roles = [
        "dasturchi",
        "direktor",
        "administrator",
        "buxgalter",
        "sotuv_agenti",
        "mentor",
        "assistent",
    ]
    return [r for r in all_roles if can_assign_role(user_role, r)]


# ---- Students (Talabalar) permissions ----

def can_create_student(user_role: Optional[str]) -> bool:
    return get_role_level(user_role) >= ROLE_LEVEL["administrator"]


def can_update_student(user_role: Optional[str]) -> bool:
    return get_role_level(user_role) >= ROLE_LEVEL["administrator"]


def can_delete_student(user_role: Optional[str]) -> bool:
    return get_role_level(user_role) >= ROLE_LEVEL["administrator"]


def can_book_student_to_group(user_role: Optional[str]) -> bool:
    """Booking is an operational action; keep it for full-access roles."""
    return get_role_level(user_role) >= ROLE_LEVEL["administrator"]


# ---- Groups (Guruhlar) permissions ----

def can_create_group(user_role: Optional[str]) -> bool:
    return get_role_level(user_role) >= ROLE_LEVEL["administrator"]


def can_update_group(user_role: Optional[str]) -> bool:
    return get_role_level(user_role) >= ROLE_LEVEL["administrator"]


def can_delete_group(user_role: Optional[str]) -> bool:
    return get_role_level(user_role) >= ROLE_LEVEL["administrator"]


# ---- Attendance (Davomatlar) ----

def can_view_attendance(_user_role: Optional[str]) -> bool:
    """Read-only access in bot: allow all authenticated roles to view."""
    return True


# ---- Reports (Hisobotlar) ----

def is_reports_allowed_in_bot() -> bool:
    """Hard disable reports via bot (financial info)."""
    return False

