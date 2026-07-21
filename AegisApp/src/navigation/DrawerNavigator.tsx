import React from 'react';
import { createDrawerNavigator } from '@react-navigation/drawer';
import type { DrawerParamList } from './types';
import Sidebar from '../components/Sidebar';
import { colors } from '../theme/colors';

import DashboardScreen from '../screens/DashboardScreen';
import CopilotScreen from '../screens/CopilotScreen';
import DocumentsScreen from '../screens/DocumentsScreen';
import EquipmentStackNavigator from './EquipmentStackNavigator';
import ComplianceScreen from '../screens/ComplianceScreen';
import IncidentsScreen from '../screens/IncidentsScreen';
import AnalyticsScreen from '../screens/AnalyticsScreen';

const Drawer = createDrawerNavigator<DrawerParamList>();

export default function DrawerNavigator() {
  return (
    <Drawer.Navigator
      drawerContent={(props) => <Sidebar {...props} />}
      screenOptions={{
        headerStyle: { backgroundColor: colors.bgElevated },
        headerTintColor: colors.textPrimary,
        headerShadowVisible: false,
        headerTitleStyle: { fontWeight: '700' },
        drawerType: 'front',
        overlayColor: 'rgba(0,0,0,0.55)',
        drawerStyle: { width: 260 },
      }}
    >
      <Drawer.Screen name="Dashboard" component={DashboardScreen} options={{ title: 'Dashboard' }} />
      <Drawer.Screen name="Copilot" component={CopilotScreen} options={{ title: 'Copilot' }} />
      <Drawer.Screen name="Documents" component={DocumentsScreen} options={{ title: 'Documents' }} />
      <Drawer.Screen
        name="EquipmentStack"
        component={EquipmentStackNavigator}
        options={{ headerShown: false, title: 'Equipment' }}
      />
      <Drawer.Screen name="Compliance" component={ComplianceScreen} options={{ title: 'Compliance' }} />
      <Drawer.Screen name="Incidents" component={IncidentsScreen} options={{ title: 'Incidents' }} />
      <Drawer.Screen name="Analytics" component={AnalyticsScreen} options={{ title: 'Analytics' }} />
    </Drawer.Navigator>
  );
}
