package com.rakings.vgc;

import android.app.Activity;
import android.appwidget.AppWidgetManager;
import android.content.Intent;
import android.os.Bundle;
import android.text.Editable;
import android.text.TextWatcher;
import android.view.View;
import android.view.ViewGroup;
import android.widget.ArrayAdapter;
import android.widget.EditText;
import android.widget.ListView;
import android.widget.RadioGroup;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.text.Normalizer;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

/** Impostazioni dei widget. CP bar: giocatore da mostrare (te o chiunque) e cosa mettere sotto (solo lui, Top 10/25/50).
 *  Per tutti i widget: il colore (gli stessi temi dell'app, predefinito Nero), che vale per tutti i widget insieme. */
public class CpImpostazioni extends Activity {
    int id = AppWidgetManager.INVALID_APPWIDGET_ID;
    String scelto = "";
    final List<String[]> tutti = new ArrayList<>();   // [nome, paese, pos, cp]
    final List<String[]> trovati = new ArrayList<>();
    ArrayAdapter<String[]> ad;
    boolean cp = true;
    String tipo = "cp";   // cp, bk (bacheca), lc (top 8 dei locali), altro
    String temaScelto;
    final java.util.List<TextView> chip = new ArrayList<>();

    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);
        setResult(RESULT_CANCELED);
        Bundle ex = getIntent().getExtras();
        if (ex != null) id = ex.getInt(AppWidgetManager.EXTRA_APPWIDGET_ID, AppWidgetManager.INVALID_APPWIDGET_ID);
        if (id == AppWidgetManager.INVALID_APPWIDGET_ID) { finish(); return; }
        setContentView(R.layout.cp_impostazioni);
        android.appwidget.AppWidgetProviderInfo info = AppWidgetManager.getInstance(this).getAppWidgetInfo(id);
        String cl = info == null || info.provider == null ? "WidgetCp" : info.provider.getClassName();
        tipo = cl.endsWith("WidgetCp") ? "cp" : cl.endsWith("WidgetBacheca") ? "bk" : cl.endsWith("WidgetLocali") ? "lc" : cl.endsWith("WidgetUsage") ? "us" : "altro";
        cp = "cp".equals(tipo);
        temaScelto = Tema.attuale(this).id;
        preparaColori();
        if (!cp) {
            findViewById(R.id.sez_cp).setVisibility(View.GONE);
            ((TextView) findViewById(R.id.titolo)).setText(R.string.cfg_widget);
            if ("bk".equals(tipo) || "lc".equals(tipo) || "us".equals(tipo)) preparaQuanti();
            findViewById(R.id.salva).setOnClickListener(v -> salva());
            return;
        }
        scelto = WidgetCp.imp(this).getString("nome_" + id, "");
        int top = WidgetCp.imp(this).getInt("top_" + id, 10);
        RadioGroup g = findViewById(R.id.quanti);
        g.check(top == 0 ? R.id.q0 : top == 25 ? R.id.q25 : top == 50 ? R.id.q50 : R.id.q10);
        TextView sc = findViewById(R.id.scelto);
        sc.setOnClickListener(v -> { scelto = ""; mostraScelto(); });   // tocco sul giocatore scelto: lo toglie (torna la soglia)
        mostraScelto();
        ListView lv = findViewById(R.id.risultati);
        ad = new ArrayAdapter<String[]>(this, android.R.layout.simple_list_item_1, trovati) {
            @Override public View getView(int pos, View cv, ViewGroup parent) {
                TextView t = (TextView) super.getView(pos, cv, parent);
                String[] x = trovati.get(pos);
                t.setText(x[0] + " · " + x[1] + "      " + Testo.ordinale(Integer.parseInt(x[2])) + " · " + x[3] + " CP");
                t.setTextColor(0xFFFFF1EF);
                t.setTextSize(14);
                return t;
            }
        };
        lv.setAdapter(ad);
        lv.setOnItemClickListener((p, v, pos, l) -> { scelto = trovati.get(pos)[0]; mostraScelto(); });
        EditText cerca = findViewById(R.id.cerca);
        cerca.addTextChangedListener(new TextWatcher() {
            public void beforeTextChanged(CharSequence s, int a, int b2, int c) { }
            public void onTextChanged(CharSequence s, int a, int b2, int c) { }
            public void afterTextChanged(Editable e) { filtra(e.toString()); }
        });
        findViewById(R.id.salva).setOnClickListener(v -> salva());
        // dati: prima i primi 150 (gia' sul telefono), poi la classifica completa scaricata in sottofondo
        caricaPrimi();
        new Thread(() -> {
            Dati.aggiorna(getApplicationContext(), false);
            JSONArray t = Dati.tutti(getApplicationContext(), true);
            runOnUiThread(() -> {
                if (t != null) {
                    tutti.clear();
                    for (int i = 0; i < t.length(); i++) {
                        JSONArray x = t.optJSONArray(i);
                        if (x != null) tutti.add(new String[]{x.optString(2), x.optString(3), String.valueOf(x.optInt(0)), String.valueOf(x.optInt(4))});
                    }
                } else caricaPrimi();
                filtra(cerca.getText().toString());
            });
        }).start();
    }

    /** valori del menu a tendina: Bacheca e Top 8 → 1, 2, 3; Top usage → Top 10/20/50/100 */
    int[] valori() { return "us".equals(tipo) ? new int[]{10, 20, 50, 100} : new int[]{1, 2, 3}; }

    /** Bacheca / Top 8 / Top usage: menu a tendina con quanti mostrarne */
    void preparaQuanti() {
        boolean bk = "bk".equals(tipo), us = "us".equals(tipo);
        findViewById(R.id.sez_n).setVisibility(View.VISIBLE);
        ((TextView) findViewById(R.id.n_titolo)).setText(bk ? R.string.cfg_n_bk : us ? R.string.cfg_n_us : R.string.cfg_n_lc);
        ((TextView) findViewById(R.id.n_nota)).setText(bk ? R.string.cfg_n_bk_nota : us ? R.string.cfg_n_us_nota : R.string.cfg_n_lc_nota);
        android.widget.Spinner s = findViewById(R.id.n_scelta);
        int[] val = valori();
        String[] et = new String[val.length];
        for (int i = 0; i < val.length; i++) et[i] = us ? "Top " + val[i] : String.valueOf(val[i]);
        ArrayAdapter<String> ad = new ArrayAdapter<String>(this, android.R.layout.simple_spinner_item, et) {
            @Override public View getView(int pos, View cv, ViewGroup parent) { return colora(super.getView(pos, cv, parent)); }
            @Override public View getDropDownView(int pos, View cv, ViewGroup parent) { return colora(super.getDropDownView(pos, cv, parent)); }
            View colora(View v) { if (v instanceof TextView) { ((TextView) v).setTextColor(0xFFFFF1EF); ((TextView) v).setTextSize(15); } return v; }
        };
        ad.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item);
        s.setAdapter(ad);
        int n = bk ? WidgetBacheca.quanti(this, id) : us ? WidgetUsage.quanti(this, id) : WidgetLocali.quanti(this, id);
        int sel = 0;
        for (int i = 0; i < val.length; i++) if (val[i] == n) sel = i;
        s.setSelection(sel);
    }

    /** pulsanti dei colori, due per riga; quello scelto e' giallo */
    void preparaColori() {
        android.widget.LinearLayout box = findViewById(R.id.colori);
        float d = getResources().getDisplayMetrics().density;
        android.widget.LinearLayout riga = null;
        for (int i = 0; i < Tema.TUTTI.length; i++) {
            final Tema t = Tema.TUTTI[i];
            if (i % 2 == 0) {
                riga = new android.widget.LinearLayout(this);
                riga.setOrientation(android.widget.LinearLayout.HORIZONTAL);
                box.addView(riga, new android.widget.LinearLayout.LayoutParams(-1, -2));
            }
            TextView c = new TextView(this);
            c.setText(t.nome);
            c.setTextSize(13);
            c.setTypeface(android.graphics.Typeface.DEFAULT_BOLD);
            c.setSingleLine(true);
            c.setEllipsize(android.text.TextUtils.TruncateAt.END);
            c.setCompoundDrawablesRelativeWithIntrinsicBounds(t.pallino, 0, 0, 0);
            c.setCompoundDrawablePadding((int) (7 * d));
            c.setPadding((int) (8 * d), (int) (7 * d), (int) (10 * d), (int) (7 * d));
            c.setTag(t.id);
            c.setOnClickListener(v -> { temaScelto = t.id; aggiornaChip(); });
            android.widget.LinearLayout.LayoutParams lp = new android.widget.LinearLayout.LayoutParams(0, -2, 1f);
            lp.setMargins((int) (3 * d), (int) (3 * d), (int) (3 * d), (int) (3 * d));
            riga.addView(c, lp);
            chip.add(c);
        }
        aggiornaChip();
    }

    void aggiornaChip() {
        for (TextView c : chip) {
            boolean on = temaScelto.equals(c.getTag());
            c.setBackgroundResource(on ? R.drawable.chip_on : R.drawable.chip);
            c.setTextColor(on ? 0xFF3A2A00 : 0xFFFFF1EF);
        }
    }

    void caricaPrimi() {
        JSONObject cp = Dati.w(this).optJSONObject("cp");
        JSONArray r = cp == null ? null : cp.optJSONArray("r");
        if (r == null) return;
        tutti.clear();
        for (int i = 0; i < r.length(); i++) {
            JSONArray x = r.optJSONArray(i);
            if (x != null) tutti.add(new String[]{x.optString(1), x.optString(2), String.valueOf(x.optInt(0)), String.valueOf(x.optInt(3))});
        }
    }

    static String n(String s) {
        return Normalizer.normalize(s == null ? "" : s, Normalizer.Form.NFD).replaceAll("\\p{M}", "").toLowerCase(Locale.ROOT).trim();
    }

    void filtra(String q) {
        trovati.clear();
        String k = n(q);
        if (k.length() >= 2) {
            for (String[] x : tutti) { if (n(x[0]).contains(k)) { trovati.add(x); if (trovati.size() >= 40) break; } }
        }
        ad.notifyDataSetChanged();
    }

    void mostraScelto() {
        TextView sc = findViewById(R.id.scelto);
        sc.setText(scelto.isEmpty() ? getString(R.string.nessun_giocatore) : "★ " + scelto + "   ✕");
    }

    void salva() {
        Tema.scegli(this, temaScelto);
        if ("bk".equals(tipo) || "lc".equals(tipo) || "us".equals(tipo)) {
            int[] val = valori();
            int pos = Math.max(0, Math.min(val.length - 1, ((android.widget.Spinner) findViewById(R.id.n_scelta)).getSelectedItemPosition()));
            ("bk".equals(tipo) ? WidgetBacheca.imp(this) : "us".equals(tipo) ? WidgetUsage.imp(this) : WidgetLocali.imp(this)).edit().putInt("n_" + id, val[pos]).apply();
            if ("us".equals(tipo)) {   // primo avvio del widget: scarica subito l'usage
                final android.content.Context app = getApplicationContext();
                new Thread(() -> { Dati.aggiorna(app, false); Dati.usage(app, true); runOnUiThread(() -> Base.ridisegnaTutti(app)); }).start();
            }
        }
        if (!cp) {
            Base.ridisegnaTutti(getApplicationContext());
            setResult(RESULT_OK, new Intent().putExtra(AppWidgetManager.EXTRA_APPWIDGET_ID, id));
            finish();
            return;
        }
        int q = ((RadioGroup) findViewById(R.id.quanti)).getCheckedRadioButtonId();
        int top = q == R.id.q0 ? 0 : q == R.id.q25 ? 25 : q == R.id.q50 ? 50 : 10;
        WidgetCp.imp(this).edit().putString("nome_" + id, scelto).putInt("top_" + id, top).apply();
        final android.content.Context app = getApplicationContext();
        new Thread(() -> {
            Dati.giocatore(app, scelto, true);
            runOnUiThread(() -> Base.ridisegnaTutti(app));
        }).start();
        Base.ridisegnaTutti(getApplicationContext());
        setResult(RESULT_OK, new Intent().putExtra(AppWidgetManager.EXTRA_APPWIDGET_ID, id));
        finish();
    }
}
