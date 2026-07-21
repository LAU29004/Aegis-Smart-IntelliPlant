import React, { useEffect } from 'react';
import { StatusBar } from 'react-native';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { DarkTheme, NavigationContainer, Theme } from '@react-navigation/native';
import { GoogleSignin } from '@react-native-google-signin/google-signin';

import { AuthProvider } from './src/context/AuthContext';
import RootNavigator from './src/navigation/RootNavigator';
import { colors } from './src/theme/colors';
import Config from 'react-native-config';
import NotificationService from './src/services/notificationService';
import { navigationRef } from "./src/navigation/navigationService";
const navTheme: Theme = {
  ...DarkTheme,
  colors: {
    ...DarkTheme.colors,
    background: colors.bg,
    card: colors.bgElevated,
    text: colors.textPrimary,
    border: colors.border,
    primary: colors.accent,
  },
};

export default function App() {
  useEffect(() => {
GoogleSignin.configure({
  webClientId: Config.GOOGLE_WEB_CLIENT_ID,
  offlineAccess: false,
});
NotificationService.initialize();
  }, []);

  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <SafeAreaProvider>
        <StatusBar
          barStyle="light-content"
          backgroundColor={colors.bgElevated}
        />

        <AuthProvider>
         <NavigationContainer ref={navigationRef} theme={navTheme}>
            <RootNavigator />
          </NavigationContainer>
        </AuthProvider>
      </SafeAreaProvider>
    </GestureHandlerRootView>
  );
}