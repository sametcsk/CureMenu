# Validation Quickstart

1. Run production-readiness and privacy tests.
2. Create two synthetic users and distinct profile/history/memory data.
3. Export the first user and verify no second-user marker exists.
4. Delete the first user with password confirmation.
5. Verify login fails and all owned relational/vector records are gone.
6. Verify the second user remains functional.
7. Start with a two-instance setting and no shared rate-limit storage; startup must fail.
8. Block optional chart/QR resources in Playwright; unrelated dashboard flows must remain usable.
9. Run the full backend and E2E suites and the source/package scanner.

Hosted HTTPS, backup restore, physical-device camera, and clinical pilot checks require dated external evidence and remain incomplete until performed.
