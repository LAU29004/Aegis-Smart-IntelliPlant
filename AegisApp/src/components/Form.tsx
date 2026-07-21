import React, { useState } from 'react';
import { StyleSheet, Text, TextInput, TextInputProps, View, Platform } from 'react-native';
import { Picker } from '@react-native-picker/picker';
import { colors, radius, spacing, typography } from '../theme/colors';

export function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <View style={styles.field}>
      <Text style={styles.label}>{label}</Text>
      {children}
    </View>
  );
}

export function LabeledInput({
  label,
  ...props
}: { label: string } & TextInputProps) {
  const [focused, setFocused] = useState(false);

  return (
    <Field label={label}>
      <View style={[styles.inputWrap, focused && styles.inputWrapFocused]}>
        <TextInput
          style={styles.input}
          placeholderTextColor={colors.textFaint}
          onFocus={(e) => {
            setFocused(true);
            props.onFocus?.(e);
          }}
          onBlur={(e) => {
            setFocused(false);
            props.onBlur?.(e);
          }}
          {...props}
        />
      </View>
    </Field>
  );
}

export function Select({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: { label: string; value: string }[];
}) {
  return (
    <Field label={label}>
      <View style={styles.pickerWrap}>
        <Picker
          selectedValue={value}
          onValueChange={(v) => onChange(String(v))}
          style={styles.picker}
          dropdownIconColor={colors.textSecondary}
        >
          {options.map((o) => (
            <Picker.Item key={o.value} label={o.label} value={o.value} color={colors.textPrimary} />
          ))}
        </Picker>
        {Platform.OS === 'ios' && <Text style={styles.chevron}>⌄</Text>}
      </View>
    </Field>
  );
}

const styles = StyleSheet.create({
  field: { marginBottom: spacing.lg ?? spacing.md * 1.5 },
  label: {
    ...typography.small,
    color: colors.textSecondary,
    marginBottom: 8,
    fontWeight: '600',
    letterSpacing: 0.4,
    textTransform: 'uppercase',
    fontSize: 11,
  },
  inputWrap: {
    backgroundColor: colors.surface2,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    ...Platform.select({
      ios: {
        shadowColor: '#000',
        shadowOpacity: 0.06,
        shadowRadius: 6,
        shadowOffset: { width: 0, height: 2 },
      },
      android: { elevation: 1 },
    }),
  },
  inputWrapFocused: {
    borderColor: colors.textPrimary,
    ...Platform.select({
      ios: {
        shadowOpacity: 0.12,
        shadowRadius: 10,
      },
      android: { elevation: 3 },
    }),
  },
  input: {
    paddingHorizontal: spacing.md,
    paddingVertical: 12,
    color: colors.textPrimary,
    fontSize: 15,
    letterSpacing: 0.1,
  },
  pickerWrap: {
    backgroundColor: colors.surface2,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    overflow: 'hidden',
    position: 'relative',
    justifyContent: 'center',
    ...Platform.select({
      ios: {
        shadowColor: '#000',
        shadowOpacity: 0.06,
        shadowRadius: 6,
        shadowOffset: { width: 0, height: 2 },
      },
      android: { elevation: 1 },
    }),
  },
  picker: { color: colors.textPrimary },
  chevron: {
    position: 'absolute',
    right: spacing.md,
    color: colors.textSecondary,
    fontSize: 18,
    pointerEvents: 'none',
  },
});