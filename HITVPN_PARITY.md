# HitVPN Parity Notes

This document tracks the public-UX parity changes between MNVPN and the HitVPN reference experience.

## Brand & copy
- `BRAND_NAME` (default `MNVPN`) — name shown in welcome and menus.
- `BRAND_TAGLINE` (default `Быстрый и безопасный VPN без логов`) — short pitch on the welcome screen.
- `PRICE_PER_DEVICE_DISPLAY` (default `100₽ / устройство / мес`) — display string for tariff line.

## Trial & referrals
- `TRIAL_DAYS=30` — long-form trial used for HitVPN-style onboarding (existing `TRIAL_HOURS` retained for short trials).
- `REFERRAL_BONUS_DAYS=15` — referral reward bumped to match HitVPN.

## Notifications
- `EXPIRY_NOTICE_DAYS=3` — how many days before subscription expiry the bot warns the user.

## Files touched
- `config.py` — added Brand block, `TRIAL_DAYS`, raised default `REFERRAL_BONUS_DAYS` to 15.
- `.env.example` — documented all new vars.
- `handlers.py` — welcome screen rewritten to surface tariff/trial/referral up-front (HitVPN-style).

## How to revert
Remove the new env vars from `.env` (defaults stay HitVPN-style) or override them to taste. No DB migrations were required.
