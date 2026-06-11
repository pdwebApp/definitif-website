// routes/clientReports.js
const express = require("express");
const path = require("path");
const { spawn } = require("child_process");

const router = express.Router();

router.post("/api/client-reports/send", async (req, res) => {
  try {
    const { clientLogins, recipientMode, manualEmails = [] } = req.body || {};

    if (!Array.isArray(clientLogins) || clientLogins.length === 0) {
      return res.status(400).json({ error: "clientLogins is required" });
    }

    if (!["default", "manual"].includes(recipientMode)) {
      return res.status(400).json({ error: "recipientMode must be 'default' or 'manual'" });
    }

    if (recipientMode === "manual" && (!Array.isArray(manualEmails) || manualEmails.length === 0)) {
      return res.status(400).json({ error: "manualEmails is required for manual mode" });
    }

    const payload = {
      clientLogins,
      recipientMode,
      manualEmails
    };

    const scriptPath = path.join(process.cwd(), "send_client_reports_batch.py");
    const python = spawn("python", [scriptPath], {
      cwd: process.cwd(),
      env: process.env
    });

    let stdout = "";
    let stderr = "";

    python.stdout.on("data", chunk => {
      stdout += chunk.toString();
    });

    python.stderr.on("data", chunk => {
      stderr += chunk.toString();
    });

    python.on("close", code => {
      if (code !== 0) {
        return res.status(500).json({
          error: "Python process failed",
          details: stderr || stdout
        });
      }

      try {
        const result = JSON.parse(stdout);
        return res.json(result);
      } catch (err) {
        return res.status(500).json({
          error: "Invalid JSON returned by Python",
          details: stdout
        });
      }
    });

    python.stdin.write(JSON.stringify(payload));
    python.stdin.end();

  } catch (err) {
    return res.status(500).json({
      error: "Unexpected server error",
      details: err.message
    });
  }
});

module.exports = router;