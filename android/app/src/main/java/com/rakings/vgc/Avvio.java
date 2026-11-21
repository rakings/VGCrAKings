package com.rakings.vgc;

import android.content.Intent;
import android.content.pm.ApplicationInfo;
import android.content.pm.PackageManager;

import com.google.androidbrowserhelper.trusted.LauncherActivity;
import com.google.androidbrowserhelper.trusted.TwaLauncher;

/**
 * Avvio dell'app. Apre il sito a schermo intero come prima, ma sceglie il browser in quest'ordine:
 * Chrome, Chrome Beta, Samsung Internet; se nessuno c'e', il browser predefinito (comportamento di prima).
 * Serve perche' alcuni browser predefiniti (per esempio Brave) non riescono ad avviarsi da soli e lasciano
 * lo schermo nero se non sono gia' aperti in background; Chrome e Samsung Internet invece si avviano sempre.
 */
public class Avvio extends LauncherActivity {

    private static final String[] PREFERITI = {
            "com.android.chrome",
            "com.chrome.beta",
            "com.sec.android.app.sbrowser",
    };

    @Override
    protected TwaLauncher createTwaLauncher() {
        String browser = scegli();
        return browser == null ? super.createTwaLauncher() : new TwaLauncher(this, browser);
    }

    private String scegli() {
        PackageManager pm = getPackageManager();
        for (String p : PREFERITI) {
            try {
                ApplicationInfo ai = pm.getApplicationInfo(p, 0);
                if (!ai.enabled) continue;
                Intent servizio = new Intent("android.support.customtabs.action.CustomTabsService").setPackage(p);
                if (pm.resolveService(servizio, 0) != null) return p;
            } catch (PackageManager.NameNotFoundException | RuntimeException e) {
                // non installato o non visibile: si prova il prossimo
            }
        }
        return null;
    }
}
