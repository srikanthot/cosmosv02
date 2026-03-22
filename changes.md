Please fix these two remaining frontend issues in the chatbot UI.

Issue 1: Broken logo in the top-left
The PSEG logo is still not rendering correctly in the top-left sidebar. It shows as a broken image.

Expected behavior:
- The logo should display properly in the sidebar across local and Azure Web App deployments
- The image path should work in production
- Use the correct Next.js static asset approach

Please check and fix:
- whether the logo file is actually present in the correct public folder
- whether the src path is wrong or case-sensitive
- whether the code is using an incorrect relative path
- whether the image should be referenced from /public using a path like /logo.png
- whether Next Image or normal img tag is being used incorrectly

Required outcome:
- logo should load correctly in Azure Web App
- no broken image icon in the top-left

Issue 2: Feedback link in Info modal footer still shows placeholder text
In the Help / Info modal footer, it still shows "Feedback form coming soon".
But the feedback URL is already configured using the frontend environment variable:
NEXT_PUBLIC_FEEDBACK_URL

Expected behavior:
- Replace the placeholder text "Feedback form coming soon" with a clickable link or button labeled "Feedback Form"
- When clicked, it should open the configured feedback form URL
- The URL must be read from process.env.NEXT_PUBLIC_FEEDBACK_URL
- This should work in the deployed Azure Web App as well

Please check and fix:
- confirm the component is actually reading process.env.NEXT_PUBLIC_FEEDBACK_URL
- confirm the environment variable name exactly matches NEXT_PUBLIC_FEEDBACK_URL
- confirm the UI is not still using hardcoded placeholder text
- if NEXT_PUBLIC_FEEDBACK_URL exists, render a clickable anchor tag
- if the variable is missing, only then show a fallback message

Suggested footer behavior:
- if feedback URL exists: show clickable "Feedback Form"
- if not: show "Feedback form coming soon"

Please make the fix directly in the frontend code and update the modal footer rendering logic.
