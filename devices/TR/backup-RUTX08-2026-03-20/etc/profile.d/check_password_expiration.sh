#!/bin/sh

change_password() {
	trap "" INT TERM QUIT HUP TSTP EXIT
	passwd && {
		echo "Password changed successfully."
		trap - INT TERM QUIT HUP TSTP EXIT
		return
	}
	echo
	check_expire
}

check_expire() {
	local password_info="$(pwage 2>/dev/null)"
	local last_change="$(echo "$password_info" | awk -F ": " '/Last password change/ {print ($2 == "N/A" ? "" : $2)}')"
	local maximum_days="$(echo "$password_info" | awk -F ": " '/Maximum days password is valid/ {print ($2 == "N/A" ? "" : $2)}')"
	local warn_days="$(echo "$password_info" | awk -F ": " '/Days before password is to expire that user is warned/ {print ($2 == "N/A" ? "" : $2)}')"

	[ -z "$last_change" ] && return
	[ -z "$maximum_days" ] || [ "$maximum_days" -eq 99999 ] && return

	local current_timestamp="$(date +%s)"
	local days_since_epoch="$((current_timestamp / (24 * 60 * 60)))"
	local days_since_change="$((days_since_epoch - last_change))"

	local days_left="$((maximum_days - days_since_change))"
	[ "$days_since_change" -lt 0 ] || [ "$days_left" -le 0 ] && {
		echo "Your password has expired, please change it."
		change_password
		return
	}

	[ -n "$warn_days" ] && [ "$days_left" -le "$warn_days" ] && {
		echo "Your password will expire in $days_left days."
	}
}

check_expire