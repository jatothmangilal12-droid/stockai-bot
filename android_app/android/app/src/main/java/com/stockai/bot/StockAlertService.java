package com.stockai.bot;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.media.AudioAttributes;
import android.media.Ringtone;
import android.media.RingtoneManager;
import android.net.Uri;
import android.os.Build;
import android.os.Handler;
import android.os.IBinder;
import android.os.Looper;
import android.os.PowerManager;
import android.os.VibrationEffect;
import android.os.Vibrator;
import android.util.Log;

import androidx.core.app.NotificationCompat;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;

public class StockAlertService extends Service {
    private static final String TAG = "StockAlertService";
    public static final String CHANNEL_BG_ID = "stockai_scanner_channel";
    public static final String CHANNEL_ALERT_ID = "stockai_breakout_loud_channel";
    public static final int NOTIF_BG_ID = 1001;

    private static StockAlertService instance;
    private boolean isRunning = false;
    private Thread scannerThread;
    private int lastSeenAlertId = -1;
    private Ringtone activeRingtone = null;
    private Handler ringtoneStopHandler = new Handler(Looper.getMainLooper());

    @Override
    public void onCreate() {
        super.onCreate();
        instance = this;
        createNotificationChannels();
        Log.d(TAG, "StockAlertService created");
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        startForeground(NOTIF_BG_ID, createForegroundNotification());

        if (!isRunning) {
            isRunning = true;
            startBackgroundScannerLoop();
        }

        return START_STICKY;
    }

    @Override
    public void onDestroy() {
        isRunning = false;
        if (scannerThread != null) {
            scannerThread.interrupt();
        }
        stopRingtone();
        instance = null;
        super.onDestroy();
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }

    public static StockAlertService getInstance() {
        return instance;
    }

    private void createNotificationChannels() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationManager nm = (NotificationManager) getSystemService(Context.NOTIFICATION_SERVICE);
            if (nm == null) return;

            // 1. Silent Background Service Channel
            NotificationChannel bgChan = new NotificationChannel(
                    CHANNEL_BG_ID,
                    "StockAI Background Scanner",
                    NotificationManager.IMPORTANCE_LOW
            );
            bgChan.setDescription("Keeps StockAI auto-scanner active to detect 5m breakouts");
            bgChan.setShowBadge(false);
            nm.createNotificationChannel(bgChan);

            // 2. High-Priority Loud Alert Channel with Alarm Sound & Vibration
            NotificationChannel alertChan = new NotificationChannel(
                    CHANNEL_ALERT_ID,
                    "StockAI Breakout Loud Alerts",
                    NotificationManager.IMPORTANCE_HIGH
            );
            alertChan.setDescription("Emergency loud alerts when high-probability 5m breakouts occur");
            alertChan.enableLights(true);
            alertChan.setLightColor(Color.RED);
            alertChan.enableVibration(true);
            alertChan.setVibrationPattern(new long[]{0, 600, 250, 600, 250, 800});
            alertChan.setLockscreenVisibility(Notification.VISIBILITY_PUBLIC);

            Uri soundUri = RingtoneManager.getDefaultUri(RingtoneManager.TYPE_ALARM);
            if (soundUri == null) {
                soundUri = RingtoneManager.getDefaultUri(RingtoneManager.TYPE_RINGTONE);
            }
            if (soundUri != null) {
                AudioAttributes audioAttributes = new AudioAttributes.Builder()
                        .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
                        .setUsage(AudioAttributes.USAGE_ALARM)
                        .build();
                alertChan.setSound(soundUri, audioAttributes);
            }

            nm.createNotificationChannel(alertChan);
        }
    }

    private Notification createForegroundNotification() {
        Intent notificationIntent = new Intent(this, MainActivity.class);
        notificationIntent.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP);
        PendingIntent pendingIntent = PendingIntent.getActivity(
                this, 0, notificationIntent,
                PendingIntent.FLAG_UPDATE_CURRENT | (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M ? PendingIntent.FLAG_IMMUTABLE : 0)
        );

        return new NotificationCompat.Builder(this, CHANNEL_BG_ID)
                .setContentTitle("🤖 StockAI Auto-Scanner Active")
                .setContentText("Scanning NSE market for 5m consolidation breakouts...")
                .setSmallIcon(R.mipmap.ic_launcher)
                .setContentIntent(pendingIntent)
                .setOngoing(true)
                .setPriority(NotificationCompat.PRIORITY_LOW)
                .build();
    }

    private void startBackgroundScannerLoop() {
        scannerThread = new Thread(new Runnable() {
            @Override
            public void run() {
                Log.d(TAG, "Starting StockAI native background scanner loop");
                while (isRunning) {
                    try {
                        checkServerForNewBreakoutAlerts();
                        Thread.sleep(12000); // Check every 12 seconds
                    } catch (InterruptedException ie) {
                        break;
                    } catch (Exception ex) {
                        Log.w(TAG, "Scanner check error: " + ex.getMessage());
                        try {
                            Thread.sleep(10000);
                        } catch (InterruptedException ignored) {}
                    }
                }
            }
        });
        scannerThread.start();
    }

    private void checkServerForNewBreakoutAlerts() {
        try {
            SharedPreferences prefs = getSharedPreferences("StockAISettings", Context.MODE_PRIVATE);
            String baseUrl = prefs.getString("server_url", "http://15.206.37.199:8000");
            if (!baseUrl.startsWith("http")) {
                baseUrl = "http://" + baseUrl;
            }

            URL url = new URL(baseUrl.replaceAll("/+$", "") + "/api/alerts/history");
            HttpURLConnection conn = (HttpURLConnection) url.openConnection();
            conn.setRequestMethod("GET");
            conn.setConnectTimeout(6000);
            conn.setReadTimeout(6000);

            int code = conn.getResponseCode();
            if (code == 200) {
                BufferedReader reader = new BufferedReader(new InputStreamReader(conn.getInputStream()));
                StringBuilder sb = new StringBuilder();
                String line;
                while ((line = reader.readLine()) != null) {
                    sb.append(line);
                }
                reader.close();

                JSONObject json = new JSONObject(sb.toString());
                if (json.optBoolean("success", false)) {
                    JSONArray alerts = json.optJSONArray("alerts");
                    if (alerts != null && alerts.length() > 0) {
                        JSONObject latest = alerts.getJSONObject(0);
                        int alertId = latest.optInt("id", 0);

                        if (lastSeenAlertId == -1) {
                            // On first service startup, sync current latest ID without alarming historical trades
                            lastSeenAlertId = alertId;
                        } else if (alertId > lastSeenAlertId) {
                            lastSeenAlertId = alertId;
                            String symbol = latest.optString("symbol", "STOCK");
                            String side = latest.optString("side", "BUY");
                            double price = latest.optDouble("price", 0.0);
                            double sl = latest.optDouble("stop_loss", 0.0);
                            double tp = latest.optDouble("target_price", 0.0);

                            triggerLoudBreakoutAlarm(symbol, side, price, sl, tp, alertId);
                        }
                    }
                }
            }
            conn.disconnect();
        } catch (Exception e) {
            Log.d(TAG, "Polling check info: " + e.getMessage());
        }
    }

    public void triggerLoudBreakoutAlarm(String symbol, String side, double price, double sl, double tp, int alertId) {
        Log.i(TAG, "🚨 TRIGGERING LOUD BREAKOUT ALARM FOR: " + symbol + " " + side + " @ " + price);

        // 1. WAKE UP MOBILE SCREEN (Even if locked / screen off)
        try {
            PowerManager pm = (PowerManager) getSystemService(Context.POWER_SERVICE);
            if (pm != null) {
                PowerManager.WakeLock wl = pm.newWakeLock(
                        PowerManager.SCREEN_BRIGHT_WAKE_LOCK | PowerManager.ACQUIRE_CAUSES_WAKEUP,
                        "stockai:breakout_alarm_wake"
                );
                wl.acquire(15000); // 15 seconds wake
            }
        } catch (Exception ex) {
            Log.w(TAG, "WakeLock error: " + ex.getMessage());
        }

        // 2. PLAY LOUD AUDIBLE ALARM SOUND DIRECTLY FROM DEVICE SPEAKER
        try {
            stopRingtone();
            Uri alarmUri = RingtoneManager.getDefaultUri(RingtoneManager.TYPE_ALARM);
            if (alarmUri == null) {
                alarmUri = RingtoneManager.getDefaultUri(RingtoneManager.TYPE_RINGTONE);
            }
            if (alarmUri == null) {
                alarmUri = RingtoneManager.getDefaultUri(RingtoneManager.TYPE_NOTIFICATION);
            }

            if (alarmUri != null) {
                activeRingtone = RingtoneManager.getRingtone(getApplicationContext(), alarmUri);
                if (activeRingtone != null) {
                    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP) {
                        activeRingtone.setAudioAttributes(new AudioAttributes.Builder()
                                .setUsage(AudioAttributes.USAGE_ALARM)
                                .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
                                .build());
                    }
                    activeRingtone.play();

                    // Automatically stop after 7 seconds so it doesn't ring endlessly
                    ringtoneStopHandler.postDelayed(new Runnable() {
                        @Override
                        public void run() {
                            stopRingtone();
                        }
                    }, 7000);
                }
            }
        } catch (Exception ex) {
            Log.w(TAG, "Audio play error: " + ex.getMessage());
        }

        // 3. VIBRATE VIGOROUSLY
        try {
            Vibrator v = (Vibrator) getSystemService(Context.VIBRATOR_SERVICE);
            if (v != null) {
                long[] pattern = new long[]{0, 600, 250, 600, 250, 800};
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                    v.vibrate(VibrationEffect.createWaveform(pattern, -1));
                } else {
                    v.vibrate(pattern, -1);
                }
            }
        } catch (Exception ex) {
            Log.w(TAG, "Vibration error: " + ex.getMessage());
        }

        // 4. DISPLAY HEADS-UP / FULLSCREEN NOTIFICATION
        try {
            NotificationManager nm = (NotificationManager) getSystemService(Context.NOTIFICATION_SERVICE);
            if (nm == null) return;

            Intent clickIntent = new Intent(this, MainActivity.class);
            clickIntent.putExtra("NAVIGATE_TO", "AI_TRADE");
            clickIntent.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP);

            PendingIntent pi = PendingIntent.getActivity(
                    this,
                    alertId > 0 ? alertId : (int) System.currentTimeMillis(),
                    clickIntent,
                    PendingIntent.FLAG_UPDATE_CURRENT | (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M ? PendingIntent.FLAG_IMMUTABLE : 0)
            );

            String title = "🚨 AI BREAKOUT ALERT: " + symbol.replace(".NS", "") + " (" + side + ")";
            String msg = symbol.replace(".NS", "") + " CMP: ₹" + String.format("%.2f", price)
                    + " | Target: ₹" + String.format("%.2f", tp)
                    + " | SL: ₹" + String.format("%.2f", sl);

            NotificationCompat.Builder nb = new NotificationCompat.Builder(this, CHANNEL_ALERT_ID)
                    .setSmallIcon(R.mipmap.ic_launcher)
                    .setContentTitle(title)
                    .setContentText(msg)
                    .setStyle(new NotificationCompat.BigTextStyle().bigText(
                            msg + "\n⚡ 60-min Consolidation Squeeze Breakout with 1.8x Volume!\nTap to review Battle-Plan & execute!"
                    ))
                    .setPriority(NotificationCompat.PRIORITY_MAX)
                    .setCategory(NotificationCompat.CATEGORY_ALARM)
                    .setVisibility(NotificationCompat.VISIBILITY_PUBLIC)
                    .setAutoCancel(true)
                    .setContentIntent(pi)
                    .setFullScreenIntent(pi, true)
                    .setVibrate(new long[]{0, 600, 250, 600, 250, 800});

            nm.notify(alertId > 0 ? alertId : 2002, nb.build());
        } catch (Exception ex) {
            Log.w(TAG, "Notification post error: " + ex.getMessage());
        }
    }

    private void stopRingtone() {
        try {
            if (activeRingtone != null && activeRingtone.isPlaying()) {
                activeRingtone.stop();
            }
        } catch (Exception ignored) {}
        activeRingtone = null;
    }
}
