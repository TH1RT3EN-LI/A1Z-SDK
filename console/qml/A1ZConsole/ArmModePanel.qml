pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts

GlassCard {
    id: root
    objectName: "armModePanel"

    required property var controller
    property bool armDraftPending: false

    ColumnLayout {
        anchors.fill: parent
        spacing: 10

        RowLayout {
            Layout.fillWidth: true
            spacing: 12
            SectionHeader {
                Layout.fillWidth: true
                theme: root.theme
                title: qsTr("机械臂模式")
            }

            Text {
                text: root.armDraftPending
                      ? qsTr("有未发送关节目标 · 模式切换已锁定")
                      : qsTr("位置保持与零力模式二选一")
                color: root.armDraftPending
                       ? root.theme.orange : root.theme.tertiaryText
                font.family: root.theme.fontFamily
                font.pixelSize: root.theme.typeCaption
            }
        }

        ArmControlModeSelector {
            Layout.fillWidth: true
            Layout.preferredHeight: 60
            theme: root.theme
            interactive: root.controller.armModeControlEnabled
                         && !root.armDraftPending
            controlMode: root.controller.controlMode
            confirmationState: root.controller.armModeState
            onModeRequested: function(zeroGravityEnabled) {
                root.controller.setGravityMode(zeroGravityEnabled)
            }
        }
    }
}
