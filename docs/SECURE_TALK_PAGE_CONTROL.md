# Wikipedia Talk Page Control System

## Overview

This system provides emergency bot control via Wikipedia discussion pages using the standard Wikipedia bot pattern: the bot periodically reads its talk page and checks for control markers.

## Architecture

```
Wikipedia Discussion Page (Discussion utilisateur:OviXCore)
        ↓
   Control Markers: {{! BOT-CONTROL: STOP }} or {{! BOT-CONTROL: RESUME }}
        ↓
   TalkPageMonitor reads page periodically
        ↓
   Kill Switch Manager
        ↓
All workers/schedulers stop or resume
```

## Standard Wikipedia Pattern

This follows the established pattern used by Wikipedia bots:
- Bot reads its talk page before operations
- Checks for specific control markers
- Responds to STOP commands immediately
- Ignores RESUME commands from Wikipedia (security)
- RESUME must be done via authenticated dashboard

## Security Features

1. **Standard Wikipedia Pattern**: Bot reads its talk page periodically (standard practice)
2. **Deterministic Markers**: Only specific markers are recognized (no AI interpretation)
3. **STOP-Only Talk Page**: Wikipedia talk page can only STOP the bot, not RESUME (for security)
4. **Dashboard Authentication**: All dashboard endpoints require Wikipedia authentication via FastAPI dependencies
5. **Authorization for RESUME**: RESUME operations require both authentication AND authorization (authorized operators only)
6. **Double Confirmation**: RESUME requires explicit "CONFIRM_RESUME" confirmation string
7. **Audit Trail**: All kill switch actions are logged

## Components

### 1. Talk Page Monitor (`talk_page_monitor.py`)

- `TalkPageMonitor`: Reads bot's talk page and detects control markers
- `parse_commands()`: Parses deterministic markers from page content
- `should_stop()`: Checks if bot should stop based on latest command
- `TalkPageCommandHandler`: Integrates with Kill Switch Manager

### 2. Kill Switch Manager (`kill_switch_manager.py`)

- `KillSwitchManager`: Centralized kill switch with persistent state
- `enable()`: Activates kill switch (STOP)
- `disable()`: Deactivates kill switch (RESUME)
- `is_enabled()`: Checks current state
- `check_and_raise()`: Final verification before edits

### 3. Dashboard API (`system.py`)

- `POST /api/system/kill-switch/activate`: Dashboard STOP (requires authentication)
- `POST /api/system/kill-switch/deactivate`: Dashboard RESUME (requires authentication + authorization + confirmation)
- `require_authenticated_user()`: FastAPI dependency for authentication
- `require_authorized_operator()`: FastAPI dependency for RESUME authorization

## Usage

### For Emergency STOP (via Wikipedia)

Add this marker to the bot's talk page:

**Page**: `Discussion utilisateur:OviXCore`

**Marker**: `{{! BOT-CONTROL: STOP }}`

The bot will:
1. Read its talk page periodically
2. Detect the STOP marker
3. Activate the kill switch immediately
4. Stop all operations

### For RESUME (via Dashboard)

RESUME must be done via the authenticated dashboard for security:

1. Login to the dashboard with Wikipedia credentials
2. Go to Kill Switch section
3. Click "Deactivate" (requires authentication + authorization)
4. Enter "CONFIRM_RESUME" confirmation
5. Bot resumes operations

**Note**: RESUME commands on Wikipedia talk page are ignored for security.

## Database Schema

### kill_switch_state Table

```sql
CREATE TABLE kill_switch_state (
    id INTEGER PRIMARY KEY,
    enabled INTEGER NOT NULL,
    reason TEXT,
    trigger_source TEXT,
    requested_by TEXT,
    requested_at TEXT,
    last_checked TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

## Security Considerations

### DOs
- Use the dashboard for RESUME operations (not talk page)
- Configure `OVIX_AUTHORIZED_OPERATORS` in production
- Monitor kill switch logs
- Use HTTPS in production for dashboard
- Keep Wikipedia credentials secure

### DON'Ts
- Attempt RESUME via Wikipedia talk page (blocked for security)
- Allow unauthorized users to perform RESUME operations
- Share dashboard credentials
- Modify the talk page with invalid markers

## Authorization Configuration

### OVIX_AUTHORIZED_OPERATORS

For production deployments, configure authorized operators via environment variable:

```bash
export OVIX_AUTHORIZED_OPERATORS="Operator1,Operator2,Operator3"
```

This environment variable specifies which Wikipedia usernames are authorized to perform RESUME operations via the dashboard. This provides an additional security layer beyond authentication.

**Behavior:**
- If `OVIX_AUTHORIZED_OPERATORS` is set: Only listed users can RESUME
- If not set: Any authenticated user can RESUME (development mode, with warning)
- STOP operations: Any authenticated user can STOP (emergency response)

**Example:**
```bash
# Production configuration
export OVIX_AUTHORIZED_OPERATORS="Badza,OviXCoreAdmin,BotOperator"

# Development (no restriction, but logs warning)
# export OVIX_AUTHORIZED_OPERATORS=""
```

## Integration with Existing System

This system integrates seamlessly with the existing Kill Switch:

- Uses same `KillSwitchManager`
- Same trigger sources (TALK_PAGE, DASHBOARD, MANUAL)
- Same database persistence
- Same final verification in Publisher
- Standard Wikipedia bot pattern

## Troubleshooting

### Bot doesn't respond to STOP marker
- Verify marker format: `{{! BOT-CONTROL: STOP }}`
- Check if bot is reading its talk page periodically
- Verify kill switch manager is initialized
- Check logs for TalkPageMonitor activity

### Dashboard RESUME not working
- Verify user is authenticated
- Check if user is in `OVIX_AUTHORIZED_OPERATORS`
- Ensure "CONFIRM_RESUME" confirmation is exact
- Check logs for authorization errors

### Kill switch state not persisting
- Verify database is initialized
- Check database permissions
- Ensure database path is correct
- Check kill_switch_state table exists

## Maintenance

### Regular Tasks

1. **Log Review**: Monitor kill switch activity
2. **Security Audit**: Review access patterns
3. **Operator List**: Keep `OVIX_AUTHORIZED_OPERATORS` updated
4. **Database Backup**: Regular backups of kill switch state

## References

- [Kill Switch Manager](../src/wikipedia_maintenance/utils/kill_switch_manager.py)
- [Talk Page Monitor](../src/wikipedia_maintenance/utils/talk_page_monitor.py)
- [API Routes](../backend/api/routes/system.py)
- [Bot Talk Page](https://fr.wikipedia.org/wiki/Discussion_utilisateur:OviXCore)
- [Bot User Page](https://fr.wikipedia.org/wiki/Utilisateur:OviXCore)