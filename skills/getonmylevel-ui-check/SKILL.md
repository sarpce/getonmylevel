---
name: getonmylevel-ui-check
description: Renders a changed web or app screen at real viewport sizes, exercises the interaction the user asked for, and checks for concrete visual and accessibility defects. Use after changing an interface that renders in a browser or app window. Not for backend-only changes or text that does not render.
---

# Check the rendered interface

A screenshot shows how the screen looks. Using it shows whether it works. Do both.

## Before changing anything

Find the established visual direction: existing components, design tokens, theme files, and neighbouring screens. Match them. Introduce a new visual style only when the user asks for one.

## Render and use it

1. Start the project's dev server or open the built page the way its README or `package.json` scripts describe.
2. Take screenshots at the widths that matter. Default to 375, 768, and 1280 px. `python scripts/screenshot.py URL` from this skill's folder does this with Playwright and also reports console errors and horizontal overflow. If Playwright is missing, use a browser tool the session already has.
3. Carry out the user's flow step by step: click, type, submit, navigate back. Check the result of each step, not only the first screen.
4. Look at the screenshots yourself before reporting.

## Defects to look for

- Text clipped, overlapping, or overflowing its container; horizontal scroll on narrow widths.
- Controls that cannot be reached or used by keyboard, or that show no visible focus.
- Low contrast text, or touch targets smaller than about 24 px.
- Missing loading, empty, error, and disabled states for the changed component.
- Console errors or failed network requests caused by the change.
- Layout that differs from neighbouring screens without a reason.

## Don't

- Don't report the UI as checked if you did not render it. Say it was not rendered and why.
- Don't judge a flow from a single screenshot.
- Don't restyle parts of the screen the user did not ask you to change.
- Don't install a browser or test framework without asking.

If nothing can render the interface in this environment, say so, list the checks above as manual steps, and still run the project's unit tests for the changed components.
