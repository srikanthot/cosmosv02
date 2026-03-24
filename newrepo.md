I have a working `frontend/` in this repository, but it is messy and currently contains generated/runtime artifacts such as `.next` and `_node_modules`. I want you to cleanly refactor it into a proper source-based, production-ready Next.js frontend while preserving the same functionality, same UI, same branding, and same backend integration.

Main goal:
- Keep the exact same user-facing functionality
- Keep the same UI and UX as closely as possible
- Keep the PSEG logo and branding
- Keep compatibility with the existing backend APIs
- Keep Azure Web App deployment compatibility
- Make the frontend clean, editable, and maintainable
- Remove generated/build/runtime clutter from the repo

Please do the following carefully:

1. Analyze the current `frontend/` and identify what is generated output versus what should be real source.
2. Reconstruct a clean editable frontend source structure using Next.js App Router if appropriate.
3. Preserve the current behavior and visual layout as closely as possible.
4. Remove the need to keep `.next`, `_node_modules`, and any other generated/build folders in source control.
5. Create a clean frontend structure like this, if appropriate:
   frontend/
     app/
       layout.js
       page.js
     components/
     public/
       pseg-logo.png
     package.json
     .env.example
     .gitignore
     README.md
     DEPLOYMENT.md
     server.js   (only keep if truly required for Azure App Service)
6. Preserve or recreate:
   - chat input
   - chat response rendering
   - citations or source section if present
   - feedback/info links if present
   - loading behavior if present
   - logo/header/footer if present
   - backend API calls
7. Update `package.json` to include proper scripts:
   - `dev`
   - `build`
   - `start`
8. Keep `server.js` only if it is actually required for Azure App Service runtime compatibility. If standard `next start` is sufficient, simplify accordingly.
9. Keep environment variables configurable via `.env.example`.
10. Create a proper `.gitignore` that excludes:
    - `.next`
    - `node_modules`
    - logs
    - env files except `.env.example`
11. Do not modify backend code.
12. Do not introduce unnecessary libraries unless needed.
13. Make the result production-ready so teammates can clone, install, run, build, and deploy it cleanly.

Very important:
- Do not blindly delete files.
- First understand the current runtime behavior.
- Then recreate a clean source-based version that preserves the same functionality and same UI as much as possible.
- If the original source is missing, reconstruct it from the current working behavior and runtime structure.
- Prefer minimal, maintainable code over hacks.
- Keep the frontend independent from the backend.

At the end, show me:
1. the final `frontend/` folder tree
2. the updated `package.json`
3. whether `server.js` was kept or removed and why
4. how to run locally
5. how to build
6. how to deploy to Azure Web App
7. which generated/runtime files were removed from source control
