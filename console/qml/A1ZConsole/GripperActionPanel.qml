pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts

GlassCard {
    id: root

    required property bool controlEnabled
    property bool draftPending: false

    signal closeRequested()
    signal releaseRequested()

    implicitHeight: 104

    RowLayout {
        anchors.fill: parent
        spacing: 10

        SectionHeader {
            Layout.fillWidth: true
            theme: root.theme
            title: qsTr("物体交互")
            subtitle: root.draftPending
                      ? qsTr("请先发送或放弃开度目标") : ""
        }

        AppButton {
            theme: root.theme
            text: qsTr("夹持并检测")
            enabled: root.controlEnabled && !root.draftPending
            onClicked: root.closeRequested()
        }

        AppButton {
            theme: root.theme
            text: qsTr("释放")
            enabled: root.controlEnabled && !root.draftPending
            onClicked: root.releaseRequested()
        }
    }
}
