import React from 'react';
import { TouchableOpacity } from 'react-native';
import { DrawerActions } from '@react-navigation/native';
import { useNavigation } from '@react-navigation/native';
import Icon from 'react-native-vector-icons/Feather';
import { colors } from '../theme/colors';

export default function MenuButton() {
  const navigation = useNavigation();
  return (
    <TouchableOpacity
      onPress={() => navigation.dispatch(DrawerActions.openDrawer())}
      hitSlop={{ top: 12, bottom: 12, left: 12, right: 12 }}
      style={{ paddingHorizontal: 8 }}
      activeOpacity={0.7}
    >
      <Icon name="menu" size={22} color={colors.textPrimary} />
    </TouchableOpacity>
  );
}