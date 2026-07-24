# Demo and product-tour guide

Task Digest includes sanitized demonstration data so contributors can explore and present the interface without connecting Asana or GitHub.

## Start the regular demo

```bash
scripts/run_demo.sh
```

The demo opens at `http://127.0.0.1:8777`.

## Start the guided tour

```bash
scripts/run_demo_tour.sh
```

The guided tour opens at `http://127.0.0.1:8777/tour` and walks through:

1. Today’s Plan
2. Search and structured filters
3. Workload metrics
4. Task and pull-request context
5. Attention and waiting work
6. The wider Task Digest toolset

Use **Next**, **Back**, the arrow keys, or **Escape**. The tour uses built-in example data and does not read local credentials.

## Record a short product demo on macOS

1. Run `scripts/run_demo_tour.sh`.
2. Press **Shift-Command-5**.
3. Choose **Record Selected Portion** and frame the browser content.
4. Record one pass through the six steps.
5. Stop the recording from the menu bar.
6. Trim the video in QuickTime Player.

Keep public recordings short (roughly 15–30 seconds), hide browser bookmarks and unrelated tabs, and use the sanitized demo instead of a real workspace.

## Static demo report

```bash
python -m task_digest --demo --open-report
```

This writes `output/demo-dashboard.html`. Static reports are useful for screenshots, but interactive dashboard actions and the guided tour require the demo server.
