# Stage 5 Step 1A — Controlled Resume Source Removal

## Goal

A resume-source page needs both creation and deletion controls. Deletion is more sensitive because a `ResumeSource` contains two connected resources:

1. a database record containing metadata and provenance, and
2. an uploaded file stored through Django's file-storage system.

This step adds a controlled removal workflow without allowing resume deletion to change the approved `CareerProfile`.

## User workflow

```text
Resume Source Control page
        ↓
click Remove
        ↓
review dedicated confirmation page
        ↓
submit POST confirmation
        ↓
delete ResumeSource database record
        ↓
after database commit, delete stored file
        ↓
return to Resume Source Control
```

The history page does not delete a file immediately when the user clicks **Remove**. The first click opens a confirmation page that identifies the exact source, filename, fingerprint, date, and active status.

## Why deletion uses a confirmation page

Deletion is destructive and cannot be undone. A direct delete link would make accidental removal too easy.

The confirmation page provides a second decision boundary:

- `GET` displays what will be deleted.
- `POST` performs the deletion.

This follows a useful web-design rule:

```text
GET reads or previews state.
POST changes state.
```

The destructive action also remains protected by Django's CSRF token.

## Database record versus stored file

Deleting a Django model with a `FileField` does not automatically guarantee that the underlying file disappears from storage.

The application therefore handles both resources deliberately:

```python
storage = source.document.storage
stored_name = source.document.name
source.delete()
transaction.on_commit(lambda: storage.delete(stored_name))
```

The database row is deleted inside a transaction. Physical file deletion is registered with `transaction.on_commit()`.

## Why `transaction.on_commit()` matters

Deleting the physical file before the database transaction succeeds could create an inconsistent state:

```text
file deleted
    ↓
database transaction fails
    ↓
database row still points to a missing file
```

Using `transaction.on_commit()` changes the order:

```text
database deletion succeeds
    ↓
transaction commits
    ↓
stored file is deleted
```

If the database transaction rolls back, the callback does not run and the source file remains available.

This is an example of coordinating two systems that do not share one transaction:

- the relational database,
- the file-storage backend.

## Active resume deletion policy

When the active resume is removed, the application does **not** automatically activate an older stored version.

That policy is intentional. Automatically selecting an older resume could silently make outdated evidence the current source of truth.

The safer state transition is:

```text
active resume deleted
        ↓
no active resume
        ↓
user explicitly selects another version
```

The success message tells the user that no resume is active and that another source must be chosen deliberately before future extraction.

Deleting an inactive version leaves the current active source unchanged.

## Career-profile safety boundary

Removing a resume source does not modify:

- professional headline,
- education summary,
- skills,
- target roles,
- preferences,
- work authorization,
- matching scores.

The current `CareerProfile` remains the approved structured profile until a later Stage 5 extraction and review workflow explicitly changes it.

## Interface behavior

A **Remove** control appears beside every stored resume version. The active-source card also exposes **Remove Resume**.

Both controls lead to the same confirmation page. The page displays:

- source label,
- original filename,
- file size,
- active or stored status,
- short SHA-256 fingerprint,
- storage date,
- warning that deletion is permanent.

For an active source, the page also warns that no older version will be activated automatically.

## Automated tests

The deletion tests verify:

1. Clicking Remove opens a confirmation page without deleting anything.
2. Removing an inactive source deletes its database row.
3. The corresponding stored file is also deleted.
4. The current active source remains active when an inactive version is removed.
5. Removing the active source leaves all older versions inactive.
6. No `CareerProfile` field or update timestamp changes.

Tests use `captureOnCommitCallbacks(execute=True)` because Django `TestCase` wraps each test in a transaction. This lets the test execute and verify the file-deletion callback without committing the entire test database transaction.

## Manual test plan

### Test 1 — Cancel deletion

1. Open Resume Source Control.
2. Click **Remove** on a stored version.
3. Confirm that the correct label, filename, fingerprint, and status appear.
4. Click **Cancel**.

Expected:

- the source still appears in version history,
- its file still opens,
- active status is unchanged.

### Test 2 — Remove an inactive version

1. Store two different resume versions.
2. Confirm that one is active and one is stored.
3. Remove the inactive version and confirm the action.

Expected:

- the inactive record disappears,
- its file is removed,
- the active resume remains active,
- the career profile is unchanged.

### Test 3 — Remove the active version

1. Store two resume versions.
2. Remove the active version and confirm the warning.

Expected:

- the active record and file are removed,
- the older version remains stored but inactive,
- the page displays **No Active Resume**,
- the user must click **Make Active** explicitly,
- the career profile remains unchanged.

## Architectural takeaway

A destructive workflow should make state transitions explicit. In this feature, safety comes from combining:

- a confirmation boundary,
- POST-only mutation,
- CSRF protection,
- database transactions,
- post-commit storage cleanup,
- no silent fallback to older evidence,
- tests for both database state and filesystem state.
