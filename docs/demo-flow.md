# Sentinel Demo Flow

This is the fastest way to present Sentinel to a recruiter, hiring manager, or interviewer in about 60 to 90 seconds.

## Goal

Show that the project is not just a chat demo. The real value is the combination of:

- role-separated access
- secure request handling
- realtime behavior
- product-minded UI
- deployment/testing readiness

## Recommended Script

### 1. Start on the landing page

Say:

`Sentinel is a secure internal messaging demo where members and admins do not share the same workspace. That product boundary is the main design idea.`

What to show:

- polished hero section
- login/register flow
- product framing

### 2. Log in as a member

Say:

`Members enter the communication workspace, where they can read and send realtime messages.`

What to show:

- live stream layout
- send message action
- recent-message search
- typing indicator

### 3. Explain the security story

Say:

`All form posts are CSRF-protected, routes are role-guarded, and the test suite covers auth, CSRF, admin restrictions, and Socket.IO flows.`

What to show:

- status feedback in the UI
- brief mention of test coverage from terminal or README

### 4. Log out and switch to admin

Say:

`Admins do not land in the chat workspace. They go to a dedicated moderation console.`

What to show:

- redirect into `/admin`
- moderation metrics
- searchable member roster
- ban / unban action

### 5. Call out the privacy boundary

Say:

`The important design choice is that admin accounts can moderate members but still cannot read or send private chat messages.`

What to show:

- admin page language
- roster-only interface
- no message history in admin view

## Demo Credentials

Fresh DB bootstrap:

- admin username: `admin`
- admin password: `AdminPass123!`

## Best Ending Line

`This project is meant to show that I can think about product UX, security boundaries, realtime features, deployment, and testability together instead of treating them as separate concerns.`

