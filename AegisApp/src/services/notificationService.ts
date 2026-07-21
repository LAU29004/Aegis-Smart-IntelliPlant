import messaging from '@react-native-firebase/messaging';
import notifee, { AndroidImportance, EventType ,   AuthorizationStatus, } from '@notifee/react-native';

import { navigate } from '../navigation/navigationService';

class NotificationService {
  /**
   * Initialize notification system
   */
  async initialize() {
    await this.createChannel();

console.log("LOCAL NOTIFICATION SENT");
    this.registerForegroundHandler();
    this.registerNotificationOpened();
    this.listenForTokenRefresh();
  }

  /**
   * Create Android notification channel
   */
  async createChannel() {
    await notifee.createChannel({
      id: 'alerts',
      name: 'Critical Alerts',
      importance: AndroidImportance.HIGH,
      vibration: true,
      sound: 'default',
    });
  }

  /**
   * Navigate to Alert Detail
   */
  private openAlert(alertId: string) {
    navigate('Main', {
      screen: 'EquipmentStack',
      params: {
        screen: 'AlertDetail',
        params: {
          id: alertId,
        },
      },
    });
  }

  /**
   * Request notification permission
   */
async requestPermission() {
  const settings = await notifee.requestPermission();

  console.log(settings);

  return (
    settings.authorizationStatus ===
    AuthorizationStatus.AUTHORIZED
  );
}

  /**
   * Get FCM Token
   */
  async getToken() {
    const token = await messaging().getToken();

    console.log('FCM TOKEN:', token);

    return token;
  }

  /**
   * Handle foreground FCM messages
   */
registerForegroundHandler() {
  messaging().onMessage(async remoteMessage => {
    console.log("Foreground Notification", remoteMessage);

    try {
      await notifee.displayNotification({
        title:
          typeof remoteMessage.data?.title === "string"
            ? remoteMessage.data.title
            : "Alert",

        body:
          typeof remoteMessage.data?.body === "string"
            ? remoteMessage.data.body
            : "",

        data: remoteMessage.data,

        android: {
          channelId: "alerts",
          importance: AndroidImportance.HIGH,
          pressAction: {
            id: "default",
          },
          autoCancel: true,
        },
      });

      console.log("✅ NOTIFICATION DISPLAYED");
    } catch (e) {
      console.log("❌ NOTIFEE ERROR");
      console.log(e);
    }
  });
}

  /**
   * Notification taps
   */
  registerNotificationOpened() {
    // App was in background
    messaging().onNotificationOpenedApp(remoteMessage => {
      console.log('Notification opened from background');

      const data = remoteMessage.data;

      if (typeof data?.alert_id === 'string') {
        this.openAlert(data.alert_id);
      }
    });

    // App was completely killed
    messaging()
      .getInitialNotification()
      .then(remoteMessage => {
        if (!remoteMessage) return;

        console.log('Notification opened from quit state');

        const data = remoteMessage.data;

        if (typeof data?.alert_id === 'string') {
          this.openAlert(data.alert_id);
        }
      });

    // User taps notification while app is open
    notifee.onForegroundEvent(({ type, detail }) => {
      if (type !== EventType.PRESS) return;

      console.log('Foreground notification pressed');

      const data = detail.notification?.data;

      if (typeof data?.alert_id === 'string') {
        this.openAlert(data.alert_id);
      }
    });
  }

  /**
   * Refresh FCM token
   */
  listenForTokenRefresh() {
    messaging().onTokenRefresh(async token => {
      console.log('New FCM Token:', token);

      /**
       * TODO
       * POST /notifications/register
       * Send updated token to backend.
       */
    });
  }
}

export default new NotificationService();
