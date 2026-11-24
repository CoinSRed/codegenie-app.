package com.portx.launcher;

import android.os.Bundle;
import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {
    @Override
    public void onCreate(Bundle savedInstanceState) {
        // Register the custom plugin before super.onCreate() builds the bridge.
        registerPlugin(GameLauncherPlugin.class);
        super.onCreate(savedInstanceState);
    }
}
