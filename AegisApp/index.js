/**
 * @format
 */

import { AppRegistry } from 'react-native';
import messaging from '@react-native-firebase/messaging';
import notifee, { AndroidImportance } from '@notifee/react-native';

import App from './App';
import { name as appName } from './app.json';

messaging().setBackgroundMessageHandler(async remoteMessage => {
  await notifee.displayNotification({
    title: remoteMessage.data?.title ?? "Alert",
    body: remoteMessage.data?.body ?? "",
    data: remoteMessage.data,
    android: {
      channelId: "alerts",
      pressAction: {
        id: "default",
      },
    },
  });
});

AppRegistry.registerComponent(appName, () => App);