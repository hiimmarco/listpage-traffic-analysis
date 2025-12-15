import os
import pandas as pd
from dotenv import load_dotenv
from analytics_connector import GA4Connector
from datetime import datetime

import json

def main():
    load_dotenv()
    credentials_path = os.path.join(os.getcwd(), 'credentials.json')
    property_id = os.getenv('GA4_PROPERTY_ID')

    if not property_id:
        print("Error: GA4_PROPERTY_ID not found in environment.")
        return

    connector = GA4Connector(credentials_path, property_id)

    # Namespaces identified from documentation
    # Removed /r/ as it represents single trips
    namespaces = [
        '/d/', '/a/', '/fr/', '/fw/', '/g/', 
        '/di/', '/tdi/', '/gdi/', '/ti/', '/gi/', 
        '/f/', '/frd/', '/fwd/', '/rbs/', '/o/', '/rl/'
    ]

    report_data = {}
    
    # Calculate dates for "last 12 months"
    start_date = '365daysAgo'
    end_date = 'today'

    print(f"Fetching data for namespaces from {start_date} to {end_date}...")
    
    results = []

    for ns in namespaces:
        # Get aggregated metrics
        agg_data = connector.get_aggregated_path_metrics(start_date, end_date, ns)
        
        # Get detailed metrics (list of URLs)
        # Note: Depending on the volume, this might take time or hit API limits.
        # Adding a small delay or handling limits might be needed if datasets are huge.
        detailed_df = connector.get_landing_page_report(start_date, end_date, ns)
        
        urls_data = []
        if not detailed_df.empty:
            # Sort by sessions descending
            detailed_df = detailed_df.sort_values(by='sessions', ascending=False)
            # Convert to list of dicts
            urls_data = detailed_df.to_dict('records')
        
        agg_data['namespace'] = ns
        results.append(agg_data)
        
        # Recommendation Logic
        # status: 'KEEP' (Green), 'EXCLUDE' (Red), 'REVIEW' (Yellow)
        recommendations_map = {
            '/d/': {'status': 'EXCLUDE', 'reason': '<strong>Base Category (Destination Only).</strong> Too broad, user intent is weak. High bounce rate indicates users are looking for more specific lists.'},
            '/a/': {'status': 'EXCLUDE', 'reason': '<strong>Base Category (Activity Only).</strong> Too broad. "Hiking" or "Biking" without a destination is rarely a useful landing page.'},
            '/di/': {'status': 'KEEP', 'reason': '<strong>Power Category (Dest + Activity).</strong> High volume, strong intent. These are our core SEO drivers. Optimize content.'},
            '/tdi/': {'status': 'KEEP', 'reason': '<strong>Power Category (Dest + Activity + Time).</strong> Very high intent (e.g., "Hiking Mallorca May"). Excellent conversion potential.'},
            '/fw/': {'status': 'KEEP', 'reason': '<strong>Route Page (Fernwanderweg).</strong> Specific product intent. Essential for capturing traffic for branded routes.'},
            '/fr/': {'status': 'KEEP', 'reason': '<strong>Route/Region Page.</strong> High value specific targeting.'},
            '/rbs/': {'status': 'EXCLUDE', 'reason': '<strong>Legacy Namespace.</strong> High bounce rate. Content likely redundant with /di/ or /fr/. Deprecate.'},
            '/g/': {'status': 'REVIEW', 'reason': '<strong>Generic/Group.</strong> Low volume. Evaluate if these queries can be served by /di/.'},
            '/ti/': {'status': 'REVIEW', 'reason': '<strong>Time + Activity.</strong> "Hiking in May". Niche, but check if content is distinct enough.'},
            '/gi/': {'status': 'REVIEW', 'reason': '<strong>Group + Activity.</strong> Niche segment. Keep if volume justifies maintenance.'},
            '/f/': {'status': 'EXCLUDE', 'reason': 'Legacy/Low Value. Consolidate.'},
            '/frd/': {'status': 'EXCLUDE', 'reason': 'Micro-segment. Likely not enough inventory to support a useful list.'},
            '/fwd/': {'status': 'EXCLUDE', 'reason': 'Micro-segment. Likely not enough inventory.'},
            '/o/': {'status': 'EXCLUDE', 'reason': 'Legacy/Obscure. Remove.'},
            '/rl/': {'status': 'REVIEW', 'reason': '<strong>Region List.</strong> Potential duplication with /d/. Check SEO cannibalization.'}, 
        }
        
        # Default for anything missed
        default_rec = {'status': 'REVIEW', 'reason': 'Analyze traffic quality and conversion.'}

        rec = recommendations_map.get(ns, default_rec)
        
        report_data[ns] = {
            "metrics": agg_data,
            "urls": urls_data,
            "recommendation": rec
        }
        
        print(f"Processed {ns}: {agg_data['sessions']} sessions. Rec: {rec['status']}")

    # Create DataFrame for initial display sorting (Namespace Summary)
    df_summary = pd.DataFrame(results)
    if not df_summary.empty:
        df_summary = df_summary.sort_values(by='sessions', ascending=False)
    
    # Executive Summary based on analysis (hardcoded for this step)
    executive_summary = """
    <div class="summary-box">
        <h3>Executive Summary & Migration Recommendations</h3>
        <p>Based on traffic volume and bounce rate analysis, we recommend a focused migration strategy:</p>
        <div style="display:flex; gap:20px; flex-wrap:wrap; margin-top:15px;">
            <div style="flex:1; min-width:250px; background:#e8f8f5; padding:15px; border-radius:4px; border-top: 4px solid #27ae60;">
                <h4 style="margin-top:0; color:#27ae60;">✅ KEEP & OPTIMIZE</h4>
                <ul style="padding-left:20px; margin-bottom:0;">
                    <li><strong>/di/ & /tdi/</strong>: The "Power Categories". These drive the majority of high-quality traffic.</li>
                    <li><strong>/fw/ & /fr/</strong>: Specific Route/Region pages are critical for capturing long-tail intent.</li>
                </ul>
            </div>
            <div style="flex:1; min-width:250px; background:#fdedec; padding:15px; border-radius:4px; border-top: 4px solid #c0392b;">
                <h4 style="margin-top:0; color:#c0392b;">❌ EXCLUDE (Do Not Generate)</h4>
                <ul style="padding-left:20px; margin-bottom:0;">
                    <li><strong>/d/ & /a/</strong>: Too broad (Destination/Activity only). Users bouncing significantly.</li>
                    <li><strong>/rbs/, /f/, /o/</strong>: Legacy namespaces with poor metrics or redundant content.</li>
                </ul>
            </div>
        </div>
        <p style="margin-top:15px; font-size:0.9em; color:#666;">* Click on any namespace in the table below to see the specific reasoning and detailed URL performance.</p>
    </div>
    """

    # --- Encryption Logic ---
    import hashlib
    import base64
    
    # Default password
    password = "listpages2025"
    
    # Simple XOR encryption with SHA256 key
    # Ideally use AES, but to avoid dependencies and keep it simple for this prototype:
    def encrypt_data(data_str, pwd):
        key = hashlib.sha256(pwd.encode('utf-8')).digest()
        data_bytes = data_str.encode('utf-8')
        encrypted = bytearray()
        for i, b in enumerate(data_bytes):
            encrypted.append(b ^ key[i % len(key)])
        return base64.b64encode(encrypted).decode('utf-8')

    print(f"Encrypting data...")
    full_data = {
        "report": report_data,
        "summary_order": df_summary['namespace'].tolist() if not df_summary.empty else []
    }
    encrypted_blob = encrypt_data(json.dumps(full_data), password)
    
    # Generate interactive HTML file
    # We use standard strings to avoid f-string conflicts with CSS and JS syntax
    html_part1 = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>List Pages Organic Traffic</title>
        <style>
            body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background-color: #f4f4f9; color: #333; display: flex; justify_content: center; padding: 20px; margin: 0; }
            .container { width: 100%; max_width: 1000px; background: white; padding: 40px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
            h1 { text-align: center; color: #2c3e50; margin-bottom: 30px; }
            
            .summary-box { background-color: #f8f9fa; border: 1px solid #e1e4e8; padding: 20px; margin-bottom: 30px; border-radius: 6px; }
            .summary-box h3 { margin-top: 0; color: #2c3e50; }
            
            .back-btn { display: none; margin-bottom: 20px; padding: 10px 15px; background-color: #2c3e50; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 14px; }
            .back-btn:hover { background-color: #34495e; }
            
            table { width: 100%; border-collapse: collapse; margin-top: 20px; }
            th, td { padding: 12px 15px; text-align: left; border-bottom: 1px solid #ddd; }
            th { background-color: #2c3e50; color: white; font-weight: 600; position: sticky; top: 0; }
            tr.clickable-row { cursor: pointer; transition: background-color 0.2s; }
            tr.clickable-row:hover { background-color: #e8f4fd; }
            td.numeric, th.numeric { text-align: right; font-variant-numeric: tabular-nums; }
            
            #table-container { overflow-x: auto; }
            .url-cell { max-width: 300px; word-wrap: break-word; white-space: normal; font-size: 0.9em; }
            
            /* Recommendation Card */
            .rec-card { margin-bottom: 20px; padding: 15px; border-radius: 6px; border-left: 6px solid #ccc; background: #fff; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
            .rec-status-KEEP { border-left-color: #27ae60; background-color: #f0fcf5; }
            .rec-status-EXCLUDE { border-left-color: #c0392b; background-color: #fdf2f2; }
            .rec-status-REVIEW { border-left-color: #f39c12; background-color: #fef9e7; }
            .rec-title { font-weight: bold; display: block; margin-bottom: 5px; font-size: 1.1em; }
            
            @media (max-width: 600px) {
                th, td { padding: 8px 10px; font-size: 14px; }
                .url-cell { max-width: 150px; }
                .container { padding: 20px; }
            }
            
            #current-view-title { font-size: 1.2em; color: #7f8c8d; margin-bottom: 10px; font-weight: normal; }
            
            /* Login Overlay */
            #login-overlay { position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: #f4f4f9; display: flex; justify_content: center; align-items: center; z-index: 999; }
            .login-box { background: white; padding: 40px; border-radius: 8px; box-shadow: 0 4px 10px rgba(0,0,0,0.1); text-align: center; width: 90%; max-width: 400px; }
            .login-box input { padding: 10px; width: 80%; margin: 20px 0; border: 1px solid #ccc; border-radius: 4px; font-size: 16px; }
            .login-box button { padding: 10px 20px; background: #2c3e50; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 16px; }
            .login-box button:hover { background: #34495e; }
            .error-msg { color: #e74c3c; margin-top: 10px; display: none; }
        </style>
    </head>
    <body>
        <!-- Login Overlay -->
        <div id="login-overlay">
            <div class="login-box">
                <h2>Protected Report</h2>
                <p>Enter password to unlock.</p>
                <input type="password" id="passwordInput" placeholder="Password" onkeyup="if(event.keyCode===13) attemptLogin()">
                <br>
                <button onclick="attemptLogin()">Unlock</button>
                <p class="error-msg" id="loginError">Incorrect password.</p>
            </div>
        </div>

        <div class="container" style="display:none;" id="mainContent">
            <h1>List Pages Organic Traffic</h1>
    """
    
    html_middle = """
            <button id="backBtn" class="back-btn" onclick="goBack()">← Back to Overview</button>
            <div id="current-view-title">Overview</div>
            <div id="rec-container"></div>
            <div id="table-container">
                <!-- Table will be rendered here -->
            </div>
        </div>

        <!-- Encrypted Data Blob -->
        <script id="encrypted-data" type="text/plain">
    """
    
    html_end = """
        </script>

        <script>
            // --- Decryption Logic ---
            async function decryptData(encryptedBase64, password) {
                // 1. Derive Key (SHA-256) - matching Python logic
                const encoder = new TextEncoder();
                const pwdData = encoder.encode(password);
                const hashBuffer = await crypto.subtle.digest('SHA-256', pwdData);
                const keyBytes = new Uint8Array(hashBuffer);

                // 2. Decode Base64
                const binaryString = atob(encryptedBase64);
                const len = binaryString.length;
                const encryptedBytes = new Uint8Array(len);
                for (let i = 0; i < len; i++) {
                    encryptedBytes[i] = binaryString.charCodeAt(i);
                }

                // 3. XOR Decrypt
                const decryptedBytes = new Uint8Array(len);
                for (let i = 0; i < len; i++) {
                    decryptedBytes[i] = encryptedBytes[i] ^ keyBytes[i % keyBytes.length];
                }

                // 4. Decode text
                const dec = new TextDecoder();
                return dec.decode(decryptedBytes);
            }

            let reportData = null;
            let summaryOrder = null;

            async function attemptLogin() {
                const pwd = document.getElementById('passwordInput').value;
                const errorMsg = document.getElementById('loginError');
                const encryptedBlob = document.getElementById('encrypted-data').textContent.trim();

                try {
                    const jsonStr = await decryptData(encryptedBlob, pwd);
                    const parsed = JSON.parse(jsonStr);
                    
                    if (parsed && parsed.report && parsed.summary_order) {
                        // Success
                        reportData = parsed.report;
                        summaryOrder = parsed.summary_order;
                        
                        document.getElementById('login-overlay').style.display = 'none';
                        document.getElementById('mainContent').style.display = 'block';
                        renderOverview();
                    } else {
                        throw new Error("Invalid structure");
                    }
                } catch (e) {
                    console.error(e);
                    errorMsg.style.display = 'block';
                    errorMsg.textContent = "Incorrect password.";
                }
            }

            // --- App Logic ---
            const container = document.getElementById('table-container');
            const recContainer = document.getElementById('rec-container');
            const backBtn = document.getElementById('backBtn');
            const viewTitle = document.getElementById('current-view-title');
            const formatPct = (val) => (val * 100).toFixed(2) + '%';
            const formatNum = (val) => val.toLocaleString();

            function renderOverview() {
                recContainer.innerHTML = ''; // Clear rec card
                let html = '<table><thead><tr><th>Namespace</th><th class="numeric">Sessions</th><th class="numeric">Bounce Rate</th><th style="width:100px;">Status</th></tr></thead><tbody>';
                
                summaryOrder.forEach(ns => {
                    const data = reportData[ns].metrics;
                    const rec = reportData[ns].recommendation;
                    
                    let statusIcon = '❓';
                    if (rec.status === 'KEEP') statusIcon = '✅ Keep';
                    if (rec.status === 'EXCLUDE') statusIcon = '❌ Kill';
                    if (rec.status === 'REVIEW') statusIcon = '⚠️ Review';
                    
                    html += `<tr class="clickable-row" onclick="showDetail('${ns}')">
                        <td>${ns}</td>
                        <td class="numeric">${formatNum(data.sessions)}</td>
                        <td class="numeric">${formatPct(data.bounce_rate)}</td>
                        <td style="text-align:center; font-size:0.9em;">${statusIcon}</td>
                    </tr>`;
                });
                
                html += '</tbody></table>';
                container.innerHTML = html;
                backBtn.style.display = 'none';
                viewTitle.textContent = 'Overview';
            }

            function showDetail(namespace) {
                const data = reportData[namespace];
                const urls = data.urls;
                const rec = data.recommendation;
                
                // Render Recommendation Card
                let recHtml = `<div class="rec-card rec-status-${rec.status}">
                    <span class="rec-title">${rec.status}: ${rec.status === 'KEEP' ? 'Migrate & Optimize' : (rec.status === 'EXCLUDE' ? 'Do Not Generate' : 'Evaluate ROI')}</span>
                    <div>${rec.reason}</div>
                </div>`;
                recContainer.innerHTML = recHtml;

                let html = '<table><thead><tr><th>URL</th><th class="numeric">Sessions</th><th class="numeric">Bounce Rate</th><th class="numeric">Revenue</th></tr></thead><tbody>';
                
                if (urls.length === 0) {
                    html += '<tr><td colspan="4">No detailed URL data found.</td></tr>';
                } else {
                    urls.forEach(row => {
                        html += `<tr>
                            <td class="url-cell"><a href="https://www.asi-reisen.de${row.landing_page}" target="_blank" style="color:#2980b9;text-decoration:none">${row.landing_page}</a></td>
                            <td class="numeric">${formatNum(row.sessions)}</td>
                            <td class="numeric">${formatPct(row.bounce_rate)}</td>
                            <td class="numeric">${formatNum(row.revenue)}</td>
                        </tr>`;
                    });
                }
                
                html += '</tbody></table>';
                container.innerHTML = html;
                backBtn.style.display = 'inline-block';
                viewTitle.textContent = `Namespace: ${namespace}`;
                history.pushState({ view: 'detail', namespace: namespace }, '', '#'+namespace);
            }

            function goBack() {
                if (history.state && history.state.view === 'detail') history.back();
                else renderOverview();
            }

            window.onpopstate = function(event) {
                if (event.state && event.state.view === 'detail') showDetail(event.state.namespace);
                else renderOverview();
            };
            
            window.addEventListener('keydown', function(e) {
                if (e.key === 'Backspace' && backBtn.style.display !== 'none') goBack();
            });

        </script>
    </body>
    </html>
    """

    # Assemble content
    full_html = (
        html_part1 + 
        executive_summary +
        html_middle + 
        encrypted_blob + 
        html_end
    )

    with open('index.html', 'w') as f:
        f.write(full_html)
    
    print("\nSuccessfully generated encrypted 'index.html'.")

if __name__ == "__main__":
    main()
