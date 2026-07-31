pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts

GlassCard {
    id: root

    required property real measured
    required property real targetDraft
    required property bool draftInitialized
    required property bool draftDirty
    required property bool draftStale
    required property bool editingEnabled
    required property bool submitEnabled
    required property bool discardEnabled

    signal targetMoved(real value)
    signal targetRequested(real value)
    signal discardRequested()

    implicitHeight: 176

    ColumnLayout {
        anchors.fill: parent
        spacing: 12

        SectionHeader {
            Layout.fillWidth: true
            theme: root.theme
            title: qsTr("目标开度")
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 10

            Text {
                text: root.measured < 0
                      ? qsTr("实际 —")
                      : qsTr("实际 %1").arg(root.measured.toFixed(3))
                color: root.theme.secondaryText
                font.family: root.theme.fontFamily
                font.pixelSize: root.theme.typeLabel
            }

            AppSlider {
                objectName: "gripperTargetSlider"

                Layout.fillWidth: true
                theme: root.theme
                from: 0.0
                to: 1.0
                value: root.targetDraft
                stepSize: 0.01
                enabled: root.editingEnabled
                Accessible.name: qsTr("夹爪目标开度")
                onMoved: root.targetMoved(value)
            }

            Text {
                Layout.preferredWidth: 112
                text: !root.draftInitialized
                      ? qsTr("目标 — · 等待回读")
                      : root.draftStale
                      ? qsTr("目标 %1 · 状态已变化").arg(
                            root.targetDraft.toFixed(2))
                      : root.draftDirty
                      ? qsTr("目标 %1 · 未发送").arg(
                            root.targetDraft.toFixed(2))
                      : qsTr("目标 %1").arg(root.targetDraft.toFixed(2))
                color: root.draftDirty || root.draftStale
                       ? root.theme.orange : root.theme.text
                font.family: "monospace"
                font.pixelSize: root.theme.typeCaption
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 10

            AppButton {
                Layout.fillWidth: true
                theme: root.theme
                kind: "primary"
                text: qsTr("发送目标")
                enabled: root.submitEnabled
                onClicked: root.targetRequested(root.targetDraft)
            }

            AppButton {
                visible: root.draftDirty
                Layout.fillWidth: true
                theme: root.theme
                kind: "quiet"
                text: qsTr("放弃修改")
                enabled: root.discardEnabled
                onClicked: root.discardRequested()
            }
        }
    }
}
