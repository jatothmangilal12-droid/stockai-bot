package com.stockai.bot;

import android.content.Context;
import android.content.SharedPreferences;
import android.os.Handler;
import android.os.Looper;
import android.webkit.JavascriptInterface;
import android.widget.Toast;

public class WebAppInterface {
    private final Context context;

    public WebAppInterface(Context context) {
        this.context = context;
    }

    @JavascriptInterface
    public boolean isNativeApp() {
        return true;
    }

    @JavascriptInterface
    public void setBackendUrl(String url) {
        if (url != null && !url.trim().isEmpty()) {
            SharedPreferences prefs = context.getSharedPreferences("StockAISettings", Context.MODE_PRIVATE);
            prefs.edit().putString("server_url", url.trim()).apply();
        }
    }

    @JavascriptInterface
    public void triggerNativeLoudAlert(final String symbol, final String side, final double price, final double sl, final double tp) {
        new Handler(Looper.getMainLooper()).post(new Runnable() {
            @Override
            public void run() {
                StockAlertService svc = StockAlertService.getInstance();
                if (svc != null) {
                    svc.triggerLoudBreakoutAlarm(
                            symbol != null ? symbol : "RELIANCE.NS",
                            side != null ? side : "BUY",
                            price > 0 ? price : 1250.0,
                            sl > 0 ? sl : 1240.0,
                            tp > 0 ? tp : 1270.0,
                            9999
                    );
                } else {
                    Toast.makeText(context, "StockAlertService starting...", Toast.LENGTH_SHORT).show();
                }
            }
        });
    }
}
