import { NavigatorScreenParams } from "@react-navigation/native";

export type RootStackParamList = {
  Login: undefined;
  Main: NavigatorScreenParams<DrawerParamList>;
};

export type DrawerParamList = {
  Dashboard: undefined;
  Copilot: undefined;
  Documents: undefined;
  EquipmentStack: NavigatorScreenParams<EquipmentStackParamList>;
  Compliance: undefined;
  Incidents: undefined;
  Analytics: undefined;
};

export type EquipmentStackParamList = {

    EquipmentList: undefined;

    EquipmentDetail: {
        id: string;
    };

    AlertDetail: {
        id: string;
    };

};
