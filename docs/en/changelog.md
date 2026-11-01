# Changelog

All notable changes to UPS Guard will be documented in this file.

## [1.0.85] - 2026-11-01

- Correct API paths and authentication examples in the user guides and related
  documentation: real-time status is `GET /api/status`; WebSocket is
  `/api/ws?token=YOUR_TOKEN`.
- Return HTTP 404 for unregistered API GET requests instead of an error body with
  HTTP 200, while preserving authentication and SPA page routing.
- Add isolated regression tests for status, authentication, WebSocket and SPA routing.
- Include the source commit in release image metadata.
- Include existing main-branch fixes for pnpm builds, dependency downloads, serial
  UPS configuration and manufacturer/model overrides.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-02-15

### 🎉 Official Release

This is the first official release of UPS Guard, marking the project's transition from beta to production-ready.

### Added - New Features

#### Security Hardening 🔒
- **API Token Authentication**: Implemented Bearer Token authentication mechanism to protect all API endpoints
  - Support environment variable `API_TOKEN` for custom authentication key
  - Auto-generate random Token and display in logs if not set
  - `/health` is public; see the current user guide for WebSocket token authentication
  - All `/api/*` routes require authentication
- **Sensitive Information Encryption**: Use Fernet symmetric encryption to protect sensitive data
  - Support environment variable `ENCRYPTION_KEY` for custom encryption key
  - Auto-generate and persist encryption key to `/data/.encryption_key`
  - Sensitive fields auto-masked when returned by API
- **CORS Tightening**: Only allow same-origin and configured subdomains to access
  - Support environment variable `ALLOWED_ORIGINS` for custom allowed origins
  - Default only allows `ups-guard` subdomain and local development environment

#### Performance Optimization 📈
- **SQLite Optimization**:
  - Enable WAL (Write-Ahead Logging) mode to improve concurrent performance
  - Set `PRAGMA synchronous=NORMAL` to reduce fsync overhead
  - Add database integrity check
- **Batch Transaction Support**: Batch write operations use transactions to improve data consistency

#### Error Recovery & Robustness 🛡️
- **gRPC Connection Enhancement**:
  - Add connection timeout mechanism (default 5 seconds)
  - Implement retry logic (up to 3 times, exponential backoff)
  - Socket reachability check before shutdown
  - Detailed error logging (distinguish connection failure vs call failure)
- **NUT Connection Recovery**:
  - Auto-reconnect mechanism (exponential backoff, max 60 seconds interval)
  - Connection status included in health check API
  - Record reconnection attempts and last error

### Changed - Feature Changes

- Update dependencies to latest secure versions:
  - `cryptography>=46.0.5` (fixes multiple security vulnerabilities)
- Health check endpoint returns more detailed information (includes NUT connection status)

### Security - Security Fixes

- Fix CORS configuration allowing all origins security issue
- Add API authentication to prevent unauthorized access
- Use encrypted storage for sensitive configuration information
- Update cryptography library to 46.0.5+ to fix known security vulnerabilities

---

## Version Notes

- **[1.0.0]**: First official release, production-ready with complete features

## Support

For questions or suggestions:
- Submit [Issue](https://github.com/KingBoyAndGirl/ups-guard/issues)
- Join [Discussions](https://github.com/KingBoyAndGirl/ups-guard/discussions)

---

**Legend**
- 🎉 Major release
- ✨ New feature
- 🔒 Security
- 🐛 Bug fix
- 📈 Performance
- 🛡️ Robustness
- 🌍 i18n
- 🔧 Configuration
