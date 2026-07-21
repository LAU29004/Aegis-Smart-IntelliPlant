import React from 'react';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import type { EquipmentStackParamList } from './types';
import EquipmentListScreen from '../screens/EquipmentListScreen';
import EquipmentDetailScreen from '../screens/EquipmentDetailScreen';
import AlertDetailScreen from '../screens/AlertDetailScreen';
import MenuButton from '../components/MenuButton';
import { colors } from '../theme/colors';

const Stack = createNativeStackNavigator<EquipmentStackParamList>();

export default function EquipmentStackNavigator() {
  return (
    <Stack.Navigator
      screenOptions={{
        headerStyle: { backgroundColor: colors.bgElevated },
        headerTintColor: colors.textPrimary,
        headerShadowVisible: false,
        contentStyle: { backgroundColor: colors.bg },
      }}
    >
      <Stack.Screen
        name="EquipmentList"
        component={EquipmentListScreen}
        options={{ title: 'Equipment', headerLeft: () => <MenuButton /> }}
      />
      <Stack.Screen
        name="EquipmentDetail"
        component={EquipmentDetailScreen}
        options={({ route }) => ({ title: route.params.id })}
      />

      <Stack.Screen

    name="AlertDetail"

    component={AlertDetailScreen}

/>
    </Stack.Navigator>
  );
}
